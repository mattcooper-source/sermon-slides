# Harvest Sermon Slide Builder — standalone website prototype

A deployable website for uploading a PDF/DOCX sermon, reviewing the text, selecting Scripture and sermon points, and exporting an experimental native ProPresenter 7 `.proBundle`.

## Start locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```
Visit http://localhost:8000.

## Deploy publicly

Build and deploy the included `Dockerfile` to a container host (Render, Railway, Fly.io, Google Cloud Run, etc.). The host will provide a public URL. Add your domain and HTTPS in the host's settings. This package **has not been hosted or published** for you.

**Security note:** The demo does not include accounts, rate limits, per-user quotas, or malware scanning. Do not expose it to unrestricted public traffic without those protections. It does not persist uploaded manuscripts. Add a privacy notice and your own retention policies before production use.

## How it works

1. Upload a manuscript (or paste its text).
2. Highlight Scripture text and click **Add selection as Scripture**. Type the *complete quoted passage* reference. Continue adding selections for a long passage, each with the same reference.
3. Highlight bold/underlined sermon points and click **Add selection as point**. Remove numbered prefixes manually if needed.
4. Add blank transitions for long commentary. Rearrange slides with up/down arrows.
5. Download the native `.proBundle` and test in ProPresenter 7.

The native bundle generator uses the supplied November 29, 2026 sample as its structural and styling reference. It clones sample ProPresenter protobuf slide records, replaces text in their RTF fields, regenerates slide identifiers, and rebuilds the ordered slide list. The bundle contains no background media. This is an **experimental, not formally documented file format**. Structural validation cannot guarantee ProPresenter will render or edit every element correctly.

## Current limitations

- Manuscript Scripture/point recognition is **not fully automatic**. The review interface helps staff select exact content so PDF emphasis and verse boundaries are not guessed.
- Slide splitting and projected line-count limits are not automatically measured. Manually split selections to three projected Scripture lines, or fewer for long lines. Four lines in the Reflow Editor may be acceptable when projected text is three lines.
- Raised verse numbers can be entered using `^18`, but superscript export needs further validation inside ProPresenter.
- Fonts match the reference sample only on machines where the same font is installed. The template uses SFT Schrifted Serif font variants. Ensure appropriate font licenses before distributing the underlying template beyond your organization.
- Export needs a full ProPresenter 7 open-and-render test. Do not use unreviewed output during a service.
- This is a standalone website, not a plugin or a hosted public link.

## Reference template

`templates/reference.proBundle` is a user-provided sample. The site ships with that template. Before distributing the website publicly, confirm you have the right to distribute any embedded fonts/creative assets and sample content. The bundle includes the slide structure and sample Scripture text, even though the app replaces visible text when generating new slides.
