export type ApiErrorShape = {
  error: {
    code: string;
    message: string;
    request_id: string;
    details?: { fields?: { field: string; issue: string }[] } & Record<string, unknown>;
  };
};

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly requestId: string;
  readonly details?: ApiErrorShape["error"]["details"];

  constructor(status: number, shape: ApiErrorShape) {
    super(shape.error.message);
    this.name = "ApiError";
    this.status = status;
    this.code = shape.error.code;
    this.requestId = shape.error.request_id;
    this.details = shape.error.details;
  }
}

export function isApiError(value: unknown): value is ApiError {
  return value instanceof ApiError;
}
