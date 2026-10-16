"use client";

import { useState, type InputHTMLAttributes, type TextareaHTMLAttributes } from "react";

type Codec<T> = { format: (value: T) => string; parse: (raw: string) => T };

export const paragraphsCodec: Codec<string[]> = {
  format: (paragraphs) => paragraphs.join("\n\n"),
  parse: (raw) =>
    raw
      .split(/\n\s*\n/)
      .map((paragraph) => paragraph.trim())
      .filter(Boolean),
};

export const linesCodec: Codec<string[]> = {
  format: (lines) => lines.join("\n"),
  parse: (raw) =>
    raw
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean),
};

export const commaListCodec: Codec<string[]> = {
  format: (items) => items.join(", "),
  parse: (raw) =>
    raw
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
};

/**
 * Text for a field whose draft value is structured (paragraphs, bullets, keywords).
 *
 * Rebuilding the text from the structure on every keystroke dropped trailing
 * spaces, new lines and blank lines, so nothing could be added at the end. The
 * field keeps what was typed and only replaces it when the value changes from
 * outside, such as a discard or a newer version.
 */
function useRawText<T>(value: T, { format, parse }: Codec<T>) {
  const [raw, setRaw] = useState(() => format(value));
  const [seen, setSeen] = useState(value);
  if (seen !== value) {
    setSeen(value);
    if (format(parse(raw)) !== format(value)) setRaw(format(value));
  }
  return [raw, setRaw] as const;
}

type Common<T> = {
  value: T;
  codec: Codec<T>;
  onValueChange: (value: T) => void;
};

export function RawTextarea<T>({
  value,
  codec,
  onValueChange,
  onBlur,
  ...props
}: Common<T> & Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "value" | "onChange">) {
  const [raw, setRaw] = useRawText(value, codec);
  return (
    <textarea
      {...props}
      value={raw}
      onChange={(event) => {
        setRaw(event.target.value);
        onValueChange(codec.parse(event.target.value));
      }}
      onBlur={(event) => {
        setRaw(codec.format(codec.parse(raw)));
        onBlur?.(event);
      }}
    />
  );
}

export function RawInput<T>({
  value,
  codec,
  onValueChange,
  onBlur,
  ...props
}: Common<T> & Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange">) {
  const [raw, setRaw] = useRawText(value, codec);
  return (
    <input
      {...props}
      value={raw}
      onChange={(event) => {
        setRaw(event.target.value);
        onValueChange(codec.parse(event.target.value));
      }}
      onBlur={(event) => {
        setRaw(codec.format(codec.parse(raw)));
        onBlur?.(event);
      }}
    />
  );
}
