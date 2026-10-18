"""Prepare a journal-club brief and inspect its portable reference package.
Does not generate images, assemble PPTX, or grant any stage approval.
"""
from __future__ import annotations
import argparse,hashlib,json,shutil,math
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote

SKILL=Path(__file__).resolve().parents[1]
PACKAGE=SKILL/'examples/academic-group-meeting'
ROLES=[
('opening','题目、文献来源与阅读问题',30),
('research-question','研究问题、对象与关键缺口',75),
('related-work','已有路线与本文定位',60),
('method','核心方法、分支、输入输出与反馈',105),
('representation-or-control','关键表征、消融或对照证据',75),
('model-or-primary-result','模型评估或主要结果',100),
('experiment-or-validation','前瞻验证或实验发现',85),
('performance-or-comparison','条件一致的性能与运行比较',100),
('mechanism-or-evidence','机制证据及解释边界',90),
('limitations','局限、待复核问题与讨论',110),
('next-step','总结、可检验的下一步与讨论',70),
]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def verify_template():
    errors=[]
    manifest=json.loads((PACKAGE/'manifest.json').read_text(encoding='utf-8'))
    for row in manifest['files']:
        path=(PACKAGE/row['path']).resolve()
        if not path.is_relative_to(PACKAGE.resolve()):
            errors.append('path escapes package: '+row['path']);continue
        if not path.is_file() or sha(path)!=row['sha256']:errors.append('missing/changed: '+row['path'])
    for row in manifest['generation_history']:
        path=PACKAGE/row['record']
        record=json.loads(path.read_text(encoding='utf-8'))
        parent=record.get('parent_record')
        if parent and not (PACKAGE/'prompts'/parent).is_file():errors.append('missing parent: '+parent)
        if not record.get('inputs'):errors.append('missing actual generation inputs: '+row['record'])
        for input_row in record.get('inputs',[]):
            ip=(PACKAGE/input_row['path']).resolve()
            if not ip.is_relative_to(PACKAGE.resolve()) or not ip.is_file() or sha(ip)!=input_row['sha256']:
                errors.append('missing/changed generation input: '+input_row['path'])
        output=record['output'];op=PACKAGE/output['path']
        if not op.is_file() or sha(op)!=output['sha256']:errors.append('missing/changed generation output: '+output['path'])
    storyboard=json.loads((PACKAGE/'storyboard.json').read_text(encoding='utf-8'))
    if not (PACKAGE/storyboard['style_anchor']['path']).is_file():errors.append('broken storyboard style anchor')
    feedback=storyboard.get('human_batch_feedback',{}).get('record')
    if feedback and not (PACKAGE/feedback).is_file():errors.append('broken storyboard acceptance record')
    class LocalLinks(HTMLParser):
        def handle_starttag(self,tag,attrs):
            for key,value in attrs:
                if key in ('href','src') and value and not urlsplit(value).scheme and not value.startswith('#'):
                    target=(PACKAGE/unquote(urlsplit(value).path)).resolve()
                    if not target.is_relative_to(PACKAGE.resolve()) or not target.is_file():errors.append('broken/nonportable gallery link: '+value)
    LocalLinks().feed((PACKAGE/'index.html').read_text(encoding='utf-8'))
    anchor=PACKAGE/manifest['style_anchor']['path']
    if sha(anchor)!=manifest['style_anchor']['sha256']:errors.append('style anchor changed')
    return {'ok':not errors,'errors':errors,'slides':len(manifest['slides']),'generation_history':len(manifest['generation_history']),'scope':'reference package integrity; not new concept or PPTX acceptance'}

def initialize(root,paper_title,minutes,mode,paper_pdf=None,intent='journal-club'):
    root=root.expanduser().resolve()
    if root.exists():return {'ok':False,'errors':['Refusing existing target; choose a new directory.'],'root':str(root)}
    if not math.isfinite(minutes) or minutes<=0 or round(minutes*60)<len(ROLES):
        return {'ok':False,'errors':['Duration must allow positive times for the proposed roles.']}
    source=paper_pdf.expanduser().resolve() if paper_pdf else None
    if source and not source.is_file():return {'ok':False,'errors':['Paper PDF not found.']}
    valid=verify_template()
    if not valid['ok']:return valid
    from apw import init_showcase
    initialized=init_showcase(root,mode=mode)
    if not initialized['ok']:return initialized
    (root/'style-reference').mkdir()
    anchor=PACKAGE/'concepts/S04.png'
    shutil.copy2(anchor,root/'style-reference/S04.png')
    shutil.copy2(SKILL/'assets/academic-group-meeting/prompt-template.md',root/'prompt-template.md')
    total=round(minutes*60)
    weights=sum(r[2] for r in ROLES)
    seconds=[1+int((total-len(ROLES))*r[2]/weights) for r in ROLES]
    seconds[-1]+=total-sum(seconds)
    slides=[{'id':f'S{i+1:02}','role':r[0],'purpose':r[1],'seconds':seconds[i],'title':'','claim':'','source_refs':[],'scientific_relationships':[],'original_evidence_panels':[],'concept_path':None} for i,r in enumerate(ROLES)]
    source_rows=[]
    if source:
        dest=root/'sources/paper.pdf';dest.parent.mkdir(exist_ok=True);shutil.copy2(source,dest)
        source_rows=[{'id':'current-paper','kind':'paper','truth_status':'verified','locator':'sources/paper.pdf; fill stable bibliography after reading','path':'sources/paper.pdf','sha256':sha(dest),'bibliography':{'title':paper_title,'doi':None,'url':None},'role':'current paper; individual claims still require reading'}]
    brief=json.loads((root/'brief.json').read_text(encoding='utf-8'))
    brief.update({'profile':'academic-group-meeting-v1','paper_title':paper_title,'audience':'研究生学术组会','goal':'科研论文精读与证据讨论' if intent=='journal-club' else '研究进展、阶段证据与下一步讨论','intent':'论文精读' if intent=='journal-club' else '研究进展汇报','duration_seconds':total,'delivery_mode':mode,'expected_slide_ids':[s['id'] for s in slides],'source_map':source_rows,'style_reference':{'path':'style-reference/S04.png','sha256':sha(anchor),'authority':'user-accepted reusable style reference; scientific content is not current-project evidence'},'page_plan':'Proposed roles only. Merge/split/reorder after reading current sources; update expected IDs and times together.','facts':'No example-paper claims or numeric results are prefilled.'})
    brief['delivery']['expected_slide_ids']=[s['id'] for s in slides]
    write_json(root/'brief.json',brief)
    write_json(root/'storyboard.json',{'duration_seconds':total,'status':'needs-paper-reading-and-story','slides':slides})
    write_json(root/'sources/evidence-map.json',{'current_paper':paper_title,'claims':[],'original_panels':[],'unverified_items':[]})
    write_json(root/'stage-state.json',{'mode':mode,'concept':{'status':'not-started','human_accepted':False},'assets':{'status':'not-started','human_accepted':False},'assembly':{'status':'not-started','human_accepted':False}})
    write_json(root/'provenance/initialization.json',{'tool':'academic_group_meeting.py','profile':'academic-group-meeting-v1','source_reference_sha256':sha(anchor),'scope':'scaffold only; not generated concepts, asset extraction, or an APW/G4 check pass'})
    (root/'provenance/stage-feedback.md').write_text('# 阶段反馈\n\n当前概念尚未生成。完成当前整批概念并检查、展示后询问用户，再等待明确反馈；素材和组装按所选范围分别执行同样检查点。工具成功不代表用户接受。\n',encoding='utf-8')
    return {'ok':True,'root':str(root),'duration_seconds':total,'proposed_roles':len(slides),'mode':mode,'intent':intent,'route':'showcase','scope':'new local academic draft through existing APW initializer; not quality or user acceptance','next':'Read current sources, replace empty claims and sources, choose per-page scientific composition, generate every planned concept with the actual reference, inspect/local-edit before inserting original panels, then ask full-batch feedback.'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    init=sub.add_parser('init',help='prepare a NEW project only, refusing existing directories')
    init.add_argument('root',type=Path);init.add_argument('--paper-title','--title',dest='paper_title',required=True)
    init.add_argument('--intent',choices=('journal-club','progress'),default='journal-club')
    init.add_argument('--minutes',type=float,default=15)
    init.add_argument('--mode',choices=('concept','assets','assembly'),default='concept')
    init.add_argument('--paper-pdf',type=Path)
    sub.add_parser('verify-template',help='verify the packaged references and generation history')
    args=parser.parse_args()
    try:
        result=verify_template() if args.command=='verify-template' else initialize(args.root,args.paper_title,args.minutes,args.mode,args.paper_pdf,args.intent)
    except (OSError,ValueError,KeyError,json.JSONDecodeError) as exc:
        result={'ok':False,'errors':[str(exc)]}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['ok'] else 1
if __name__=='__main__':raise SystemExit(main())
