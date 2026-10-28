import { useRef, useState } from "react";
import { AlertTriangle, FileText, Info, Loader2, UploadCloud } from "lucide-react";
import { cn } from "@/lib/utils";

export interface EngineFailure {
  message: string;
  detail?: string;
}

const PREVIEW_BYTES = 64 * 1024;
const PREVIEW_LINES = 8;

function fmtSize(b: number) {
  return b < 1024 ? `${b} B` : b < 1048576 ? `${(b / 1024).toFixed(1)} KB` : `${(b / 1048576).toFixed(1)} MB`;
}

export function UploadCard({ onRun, loading, error, notice }: {
  onRun: (f: File) => void;
  loading: boolean;
  error: EngineFailure | null;
  notice?: string;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const pick = async (f?: File) => {
    if (!f) return;
    setFile(f);
    // Raw lines for a glance only; the API owns CSV parsing.
    const head = await f.slice(0, PREVIEW_BYTES).text();
    setPreview(head.split(/\r?\n/).slice(0, PREVIEW_LINES).join("\n"));
  };

  return (
    <div id="upload" className="card-soft scroll-mt-6 p-5 sm:p-6">
      <h2 className="text-lg font-bold">Upload CSV</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Columns <code className="font-mono">id,text,date,label</code>. Rows with an empty label are checked.
      </p>
      <button
        type="button"
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          pick(e.dataTransfer.files[0]);
        }}
        className={cn(
          "mt-4 flex w-full flex-col items-center gap-2 rounded-2xl border-2 border-dashed px-4 py-8 text-center transition",
          over ? "border-primary bg-accent" : "border-track bg-muted/50 hover:border-primary",
        )}
      >
        <UploadCloud className="size-8 text-primary" />
        <span className="text-sm font-semibold text-heading">Drop a CSV here, or click to choose</span>
      </button>
      <input ref={input} type="file" accept=".csv,text/csv" className="hidden" onChange={(e) => pick(e.target.files?.[0])} />
      {file && (
        <div className="mt-4 space-y-3">
          <div className="flex items-center gap-3 text-sm">
            <FileText className="size-4 shrink-0 text-primary" />
            <span className="min-w-0 truncate font-semibold text-heading">{file.name}</span>
            <span className="shrink-0 text-muted-foreground">{fmtSize(file.size)}</span>
          </div>
          <div>
            <p className="mb-1 text-xs text-muted-foreground">First lines of the file, unparsed</p>
            <pre className="max-h-48 overflow-auto rounded-2xl bg-muted p-4 font-mono text-xs leading-relaxed text-foreground">
              {preview || "(empty file)"}
            </pre>
          </div>
        </div>
      )}
      <button
        disabled={!file || loading}
        onClick={() => file && onRun(file)}
        className="mt-4 inline-flex h-11 items-center justify-center gap-2 rounded-full bg-primary px-6 text-sm font-semibold text-primary-foreground shadow-soft transition hover:opacity-90 disabled:opacity-50"
      >
        {loading && <Loader2 className="size-4 animate-spin" />}
        {loading ? "Running…" : "Run the engine"}
      </button>
      {notice && !error && (
        <div role="status" className="mt-4 flex gap-2 rounded-2xl bg-warn-soft p-4 text-sm text-warn">
          <Info className="mt-0.5 size-4 shrink-0" />
          <span>{notice}</span>
        </div>
      )}
      {error && (
        <div role="alert" className="mt-4 rounded-2xl bg-bad-soft p-4 text-bad">
          <div className="flex items-center gap-2 font-semibold">
            <AlertTriangle className="size-4" />
            {error.message}
          </div>
          {error.detail && <p className="mt-1 break-words font-mono text-xs">{error.detail}</p>}
          <p className="mt-2 text-xs opacity-80">No verdicts are shown when the engine fails.</p>
        </div>
      )}
    </div>
  );
}
