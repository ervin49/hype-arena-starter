// Shapes from contract v1 (plan §5) and the HTTP contract (plan §6.5).
// Field names are fixed by the team contract; do not rename.

export type Label = "true" | "false" | "unsure";

export interface InputRow {
  id: string;
  text: string;
  date: string;
  label: "" | Label;
}

export type ValueOp = "eq" | "lt" | "le" | "gt" | "ge";

export interface ClaimedValue {
  kind:
    | "quantity"
    | "money"
    | "percent"
    | "date"
    | "version"
    | "duration"
    | "name"
    | "boolean";
  value: string | number | boolean;
  unit?: string;
  currency?: string;
  per?: string;
  op?: ValueOp;
  [extra: string]: unknown;
}

export interface Fact {
  subject: string;
  attribute: string;
  value: ClaimedValue;
}

export interface Extraction {
  facts: Fact[];
  complete: boolean;
  issues: string[];
}

export interface Prediction {
  id: string;
  label: Label;
  confidence: number | null;
  evidence_ids: string[];
  reason: string;
  extraction?: Extraction;
}

export interface PredictResponse {
  predictions: Prediction[];
  demo_mode: boolean;
}

export interface PredictCsvResponse extends PredictResponse {
  rows: InputRow[];
}

export interface ApiError {
  error: string;
  detail?: string;
}
