import { z } from "zod";

export const strongPasswordSchema = z
  .string()
  .min(8, "At least 8 characters")
  .max(128, "Use no more than 128 characters")
  .regex(/[A-Za-z]/, "Include a letter")
  .regex(/\d/, "Include a digit");

export const resetPasswordSchema = z
  .object({
    password: strongPasswordSchema,
    confirmPassword: z.string(),
    code: z.string().trim().max(512, "Paste the code from your email"),
  })
  .refine((values) => values.password === values.confirmPassword, {
    message: "Passwords must match",
    path: ["confirmPassword"],
  });
