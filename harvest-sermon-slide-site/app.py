from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Literal
import io, re
from builder import to_bundle

BASE=Path(__file__).parent
app=FastAPI(title='Harvest Sermon Slide Builder',version='0.1.0')
app.mount('/static',StaticFiles(directory=BASE/'static'),name='static')

class Slide(BaseModel):
    type:Literal['scripture','point','blank']='scripture'
    text:str=''
    reference:str=''
class BuildRequest(BaseModel):
    title:str=Field(default='Sermon Slides',max_length=100)
    slides:list[Slide]=Field(min_length=1,max_length=300)

@app.get('/',response_class=HTMLResponse)
def index():return (BASE/'static'/'index.html').read_text()

@app.post('/api/extract')
async def extract(file:UploadFile=File(...)):
    data=await file.read()
    if len(data)>12*1024*1024:raise HTTPException(413,'12 MB maximum upload')
    name=(file.filename or '').lower()
    try:
        if name.endswith('.pdf'):
            import fitz
            doc=fitz.open(stream=data,filetype='pdf')
            if len(doc)>100:raise ValueError('Maximum 100 pages')
            # preserve original text for review; do not silently invent missing Scriptures.
            pages=[page.get_text(sort=True) for page in doc]
            text='\n\n'.join(pages)
        elif name.endswith('.docx'):
            from docx import Document
            doc=Document(io.BytesIO(data))
            text='\n'.join(p.text for p in doc.paragraphs)
        else:raise HTTPException(400,'Upload PDF or Word .docx')
    except HTTPException:raise
    except Exception as e:raise HTTPException(422,f'Could not read document: {e}')
    title=next((line.strip() for line in text.splitlines() if line.strip()),'Sermon Slides')
    # Candidate recognition is intentionally conservative: extraction is a draft,
    # users must review and add exact Scripture quotes and underlined points.
    refs=re.findall(r'(?i)(?:[1-3](?:st|nd|rd)?\s+)?(?:Corinthians|Romans|Ephesians|Galatians|John|Matthew|Mark|Luke|Acts|Philippians|Colossians|Psalms|Genesis|Exodus|Hebrews|James|Peter|Timothy)\s+\d+:\d+(?:\s*[–-]\s*\d+)?',text)
    return {'title':title,'text':text[:120000],'references':list(dict.fromkeys(refs)), 'notice':'Review manuscript and manually select all quotations and bold/underlined points. Plain PDF text extraction cannot reliably identify underline and emphasis.'}

@app.post('/api/build')
def build(request:BuildRequest):
    try:content=to_bundle([s.model_dump() for s in request.slides],request.title)
    except Exception as e:raise HTTPException(422,str(e))
    filename=re.sub(r'[^a-zA-Z0-9_-]+','_',request.title).strip('_')[:65] or 'Sermon_Slides'
    return Response(content,media_type='application/octet-stream',headers={'Content-Disposition':f'attachment; filename="{filename}.proBundle"','Cache-Control':'no-store'})

@app.get('/api/health')
def health():return {'ok':True,'native_format':'ProPresenter 7 protobuf (experimental)','render_verified':False}
