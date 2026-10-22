"""Create aligned English/Arabic captions and burn them into the narrated MP4."""

from __future__ import annotations

import argparse
import asyncio
import re
import subprocess
import sys
from pathlib import Path

import edge_tts
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def voice_settings():
    from demo.scripts.build_walkthrough_video import NARRATION, RATE, VOICE

    return NARRATION, RATE, VOICE


DEFAULT_VIDEO = ROOT / "demo/output/financial_document_assistant_walkthrough_final.mp4"
DEFAULT_OUTPUT = ROOT / "demo/output/financial_document_assistant_walkthrough_en_ar.mp4"
DEFAULT_SRT = ROOT / "demo/output/financial_document_assistant_captions_en_ar.srt"
DEFAULT_ASS = ROOT / "demo/output/financial_document_assistant_captions_en_ar.ass"

# English units are kept verbatim from the spoken script for word-level sync.
CAPTIONS = [
    ("Welcome to Impact Finance.", "مرحبًا بكم في Impact Finance."),
    ("This walkthrough follows a document from intake", "يستعرض هذا الفيديو المستند منذ استلامه"),
    ("through review, recording, reporting, and spreadsheet delivery.", "مرورًا بالمراجعة والتسجيل والتقارير وإرسال البيانات إلى جدول البيانات."),
    ("At the top of the finance dashboard,", "من أعلى لوحة الشؤون المالية،"),
    ("choose US dollars, euros, or Egyptian pounds", "اختر الدولار الأمريكي أو اليورو أو الجنيه المصري"),
    ("as the reporting currency.", "كعملة لعرض التقارير."),
    ("Confirmed spending, categories, and monthly trends convert together,", "تُحوَّل المصروفات المؤكدة والفئات والاتجاهات الشهرية معًا،"),
    ("while each expense keeps its original invoice currency and amount.", "مع الاحتفاظ بعملة الفاتورة الأصلية ومبلغها لكل مصروف."),
    ("The exchange-rate panel shows the currency pairs,", "تعرض لوحة أسعار الصرف أزواج العملات،"),
    ("provider, and rate update date, so the conversion is transparent.", "ومصدر الأسعار وتاريخ تحديثها، لتكون عملية التحويل واضحة."),
    ("Select a project and upload invoices or receipts", "اختر مشروعًا وارفع الفواتير أو الإيصالات"),
    ("as PDFs and images, one at a time or in a batch.", "بصيغة PDF أو كصور، منفردة أو ضمن دفعة واحدة."),
    ("Documents can also arrive through the connected Google Drive intake.", "يمكن أيضًا استلام المستندات من مجلد Google Drive المرتبط."),
    ("Processing status appears as the batch moves through the queue.", "وتظهر حالة المعالجة أثناء انتقال الملفات عبر قائمة الانتظار."),
    ("For each document, compare the original with the extracted", "لكل مستند، قارن الأصل بالبيانات المستخرجة"),
    ("vendor, date, invoice number, totals, tax, discount, and currency.", "من اسم المورد والتاريخ ورقم الفاتورة والإجماليات والضريبة والخصم والعملة."),
    ("The system keeps supporting evidence with the result.", "يحتفظ النظام بالأدلة الداعمة مع النتيجة."),
    ("Clear records can be automatically recorded when that option is enabled;", "يمكن تسجيل المستندات الواضحة تلقائيًا عند تفعيل هذا الخيار؛"),
    ("uncertain fields and possible duplicates are held for a person to review.", "أما الحقول غير المؤكدة والتكرارات المحتملة فتُحال إلى المراجع."),
    ("On the review screen, inspect the original page,", "في شاشة المراجعة، افحص الصفحة الأصلية،"),
    ("correct values that are missing or misread, choose a category, and revalidate.", "وصحّح القيم الناقصة أو المقروءة خطأً، واختر فئة ثم أعد التحقق."),
    ("The validation panel explains issues such as missing currency or a possible duplicate.", "توضح لوحة التحقق مشكلات مثل غياب العملة أو احتمال التكرار."),
    ("A reviewer can confirm a corrected record or dismiss a document,", "يمكن للمراجع اعتماد السجل بعد تصحيحه أو استبعاد المستند،"),
    ("with a reason when required.", "مع ذكر السبب عند الحاجة."),
    ("This keeps unverified expenses out of confirmed spending", "وبهذا تبقى المصروفات غير المتحقق منها خارج إجمالي المصروفات المؤكدة"),
    ("until a human decision is made.", "حتى يتخذ شخص قرار المراجعة."),
    ("Once confirmed, records appear in the expense tracker", "بعد الاعتماد، تظهر السجلات في متتبع المصروفات"),
    ("and the totals and charts update.", "وتتحدث الإجماليات والرسوم البيانية."),
    ("The reporting-currency selector changes the view without rewriting source records.", "يغيّر محدد عملة التقارير طريقة العرض من دون تعديل السجلات الأصلية."),
    ("The Operations page provides pipeline status, processing stages, events,", "تعرض صفحة العمليات حالة مسار المعالجة ومراحله والأحداث،"),
    ("and estimated model spend, making it easier to investigate a run.", "والتكلفة التقديرية للنموذج، لتسهيل تتبع أي عملية."),
    ("Automatic extraction is not the final authority:", "الاستخراج التلقائي ليس القرار النهائي:"),
    ("original previews and supporting page evidence remain available,", "إذ تظل معاينة المستند وأدلة الصفحات متاحة،"),
    ("and validation checks amounts, currency, dates, and possible duplicates.", "ويتحقق النظام من المبالغ والعملات والتواريخ والتكرارات المحتملة."),
    ("When a value cannot be verified, the review queue makes that uncertainty visible", "عندما يتعذر التحقق من قيمة، تعرض قائمة المراجعة ذلك بوضوح"),
    ("instead of quietly adding it to confirmed totals.", "بدلًا من إضافتها بصمت إلى الإجماليات المؤكدة."),
    ("The expense tracker can be filtered by project, category, source currency, and date,", "يمكن تصفية متتبع المصروفات حسب المشروع والفئة وعملة المصدر والتاريخ،"),
    ("while Operations keeps a traceable run history.", "فيما تحتفظ صفحة العمليات بسجل يمكن تتبعه."),
    ("Categories and projects can be maintained in the workspace.", "يمكن إدارة الفئات والمشاريع من مساحة العمل."),
    ("The Integrations page documents the shared-folder Drive workflow", "توضح صفحة التكاملات سير العمل مع مجلد Drive المشترك"),
    ("and Google Sheets projection, along with other automation options.", "وربط Google Sheets، إلى جانب خيارات أتمتة أخرى."),
    ("Here, the synced expense rows are visible in the spreadsheet.", "وهنا تظهر صفوف المصروفات المتزامنة داخل جدول البيانات."),
    ("That is the complete flow: bring documents in,", "هكذا تكتمل العملية: استيراد المستندات،"),
    ("review evidence, confirm records, and track spending consistently across currencies.", "ومراجعة الأدلة واعتماد السجلات وتتبع الإنفاق بوضوح عبر العملات."),
]


def tokens(value: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9]+(?:'[A-Za-z]+)?", value.casefold())


async def word_boundaries() -> list[dict]:
    narration, rate, voice = voice_settings()
    communicate = edge_tts.Communicate(
        narration, voice=voice, rate=rate, boundary="WordBoundary"
    )
    marks = []
    async for item in communicate.stream():
        if item["type"] == "WordBoundary":
            marks.append(item)
    if not marks:
        raise RuntimeError("Speech service returned no word-timing metadata")
    return marks


def align_captions(marks: list[dict]) -> list[tuple[float, float, str, str]]:
    spoken = [token for mark in marks for token in tokens(mark.get("text", ""))]
    mark_for_token = [mark for mark in marks for _ in tokens(mark.get("text", ""))]
    cursor = 0
    previous_end = 0.0
    aligned = []
    for english, arabic in CAPTIONS:
        wanted = tokens(english)
        found = None
        for start in range(cursor, len(spoken) - len(wanted) + 1):
            if spoken[start : start + len(wanted)] == wanted:
                found = start
                break
        if found is None:
            raise RuntimeError(f"Could not align caption text to narration: {english}")
        start_mark = mark_for_token[found]
        end_mark = mark_for_token[found + len(wanted) - 1]
        start = max(previous_end, 0.0, start_mark["offset"] / 10_000_000 - 0.04)
        end = (end_mark["offset"] + end_mark["duration"]) / 10_000_000 + 0.16
        aligned.append((start, end, english, arabic))
        previous_end = end
        cursor = found + len(wanted)
    return aligned


def srt_time(seconds: float) -> str:
    total_ms = round(seconds * 1000)
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def ass_time(seconds: float) -> str:
    total_cs = round(seconds * 100)
    hours, rem = divmod(total_cs, 360_000)
    minutes, rem = divmod(rem, 6_000)
    secs, centis = divmod(rem, 100)
    return f"{hours}:{minutes:02}:{secs:02}.{centis:02}"


def write_subtitles(rows: list[tuple[float, float, str, str]], srt: Path, ass: Path) -> None:
    srt_chunks = []
    dialogues = []
    for index, (start, end, english, arabic) in enumerate(rows, 1):
        srt_chunks.append(
            f"{index}\n{srt_time(start)} --> {srt_time(end)}\n{english}\n{arabic}"
        )
        text = english.replace("{", "\\{").replace("}", "\\}")
        ar = arabic.replace("{", "\\{").replace("}", "\\}")
        dialogues.append(
            f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Default,,0,0,0,,"
            f"{{\\rEnglish}}{text}\\N{{\\rArabic}}{ar}"
        )
    srt.write_text("\n\n".join(srt_chunks) + "\n", encoding="utf-8-sig")
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1026
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,38,&H00FFFFFF,&H0000FFFF,&H00101010,&H90000000,0,0,0,0,100,100,0,0,3,1.5,0.5,2,110,110,34,1
Style: English,Arial,38,&H00FFFFFF,&H0000FFFF,&H00101010,&H90000000,0,0,0,0,100,100,0,0,3,1.5,0.5,2,110,110,34,1
Style: Arabic,Tahoma,40,&H00FFFFFF,&H0000FFFF,&H00101010,&H90000000,0,0,0,0,100,100,0,0,3,1.5,0.5,2,110,110,34,178

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ass.write_text(header + "\n".join(dialogues) + "\n", encoding="utf-8-sig")


def burn(video: Path, ass: Path, output: Path) -> None:
    if not video.is_file():
        raise FileNotFoundError(video)
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing captioned video: {output}")
    ass_relative = ass.resolve().relative_to(ROOT).as_posix()
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video),
            "-vf",
            f"ass={ass_relative}",
            "-map",
            "0:v:0",
            "-map",
            "0:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(output),
        ],
        cwd=ROOT,
        check=True,
    )


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, default=DEFAULT_VIDEO)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--srt", type=Path, default=DEFAULT_SRT)
    parser.add_argument("--ass", type=Path, default=DEFAULT_ASS)
    args = parser.parse_args()
    for path in (args.output, args.srt, args.ass):
        path.parent.mkdir(parents=True, exist_ok=True)
    marks = await word_boundaries()
    rows = align_captions(marks)
    write_subtitles(rows, args.srt, args.ass)
    burn(args.video, args.ass, args.output)
    print(f"Captioned video: {args.output}")
    print(f"English/Arabic captions: {args.srt}")
    print(f"Aligned caption cues: {len(rows)}")


if __name__ == "__main__":
    asyncio.run(main())
