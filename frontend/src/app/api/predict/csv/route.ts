import { NextResponse } from "next/server";
import { DEMO, demoCsv, forward } from "@/lib/upstream";

export const dynamic = "force-dynamic";

// The CSV is parsed by the API (C), never here: this route only checks that a
// file is present and forwards it unchanged in the multipart field "file".
export async function POST(req: Request) {
  let form: FormData;
  try {
    form = await req.formData();
  } catch {
    return NextResponse.json({ error: "Expected a multipart upload." }, { status: 400 });
  }
  const file = form.get("file");
  if (!(file instanceof File) || file.size === 0) {
    return NextResponse.json({ error: 'No file in the "file" field.' }, { status: 400 });
  }
  if (DEMO) return NextResponse.json(demoCsv());

  const out = new FormData();
  out.append("file", file, file.name);
  return forward("/predict/csv", { method: "POST", body: out });
}
