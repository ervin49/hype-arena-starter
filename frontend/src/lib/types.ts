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

// A practice row cited as evidence, sent by the API with its text.
export interface EvidenceRow {
  id: string;
  text: string;
  date: string;
  label: "" | Label;
}

export interface Prediction {
  id: string;
  label: Label;
  confidence: number | null;
  evidence_ids: string[];
  // The cited rows with their text; older API versions send ids only.
  evidence?: EvidenceRow[];
  reason: string;
  extraction?: Extraction;
  // Set by the API when the engine failed on this row.
  error?: string;
}

export interface PredictResponse {
  predictions: Prediction[];
  demo_mode: boolean;
}

export interface PredictCsvResponse extends PredictResponse {
  rows: InputRow[];
}

export type ClaimType = "fact" | "compare" | "change" | "at_event" | "relation";

// A generated claim, as the batch run writes it to output.csv (label is always true).
export interface Claim {
  id: string;
  type: ClaimType;
  text: string;
  form: Record<string, unknown>;
  confidence: number;
  evidence_ids: string[];
  evidence: EvidenceRow[];
}

export interface ClaimsResponse {
  claims: Claim[];
  // Counts from the generator: candidates.<type>, rejected.<reason>, selected.<type>, selected.
  report: Record<string, number>;
  as_of: string;
  demo_mode: boolean;
}

// GET /metrics (PLAN_NEXT.md section 5): measured calibration, or null when not measured.
export interface LabelBin {
  label: Label;
  from: number;
  to: number;
  n: number;
  // How often labels in this band were right, out of fold.
  accuracy: number;
  // The confidence the engine reports for this band.
  confidence: number;
}

export interface LabelCalibration {
  method: string;
  fitted_on: string;
  bins: LabelBin[];
  ece_before: number | null;
  ece_after: number | null;
}

export interface ClaimGroup {
  group: string;
  n: number;
  right: number;
  // Share of the group's backtested claims that were true after the cut-off.
  precision: number;
  confidence: number;
}

export interface ClaimCalibration {
  cutoffs: string[];
  groups: ClaimGroup[];
}

export interface MetricsResponse {
  labels: LabelCalibration | null;
  claims: ClaimCalibration | null;
  // True only when this frontend serves its fixture instead of the API's numbers.
  simulated: boolean;
}

export interface ApiError {
  error: string;
  detail?: string;
}
