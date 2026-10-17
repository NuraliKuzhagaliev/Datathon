"""Build the versioned, synthetic-only integration contract for both developers."""
from pathlib import Path
import base64, io, json
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parent
def obj(props, required=None):
    return {'type':'object','additionalProperties':False,'properties':props,'required':list(props) if required is None else required}
def arr(item, **kwargs): return {'type':'array','items':item,**kwargs}
def ref(name): return {'$ref':f'#/components/schemas/{name}'}
def string(**kwargs): return {'type':'string',**kwargs}
def number(**kwargs): return {'type':'number',**kwargs}
def enum(*values): return string(enum=list(values))
def nullable(schema): return {'anyOf':[schema,{'type':'null'}]}
schemas={}
schemas['Error']=obj({'error':obj({'code':string(),'message':string()})})
schemas['UploadAccepted']=obj({'job_id':string(minLength=1)})
schemas['EvidenceFrame']=obj({'timestamp_sec':number(minimum=0),'image_base64':string(minLength=4,contentEncoding='base64',contentMediaType='image/jpeg')})
schemas['Violation']=obj({'type':string(minLength=1),'timecode_sec':number(minimum=0),'description':string(minLength=1),'evidence_frames':arr(ref('EvidenceFrame'),minItems=1,maxItems=3)})
schemas['Processing']=obj({'job_id':string(),'status':{'const':'processing','type':'string'}})
schemas['Failed']=obj({'job_id':string(),'status':{'const':'failed','type':'string'},'error':obj({'code':string(),'message':string()})})
schemas['DonePositive']=obj({'job_id':string(),'status':{'const':'done','type':'string'},'verdict':{'const':'violation','type':'string'},'violations':arr(ref('Violation'),minItems=1)})
schemas['DoneNegative']=obj({'job_id':string(),'status':{'const':'done','type':'string'},'verdict':{'const':'no_violation','type':'string'},'violations':arr(ref('Violation'),maxItems=0)})
schemas['JuryResult']={'oneOf':[ref('Processing'),ref('Failed'),ref('DonePositive'),ref('DoneNegative')]}
schemas['Rule']=obj({'rule_id':string(),'display_name':string(),'document_title':string(),'source_url':string(format='uri'),'clause':string(),'revision':string(),'effective_date':nullable(string(format='date')),'applicability':string(),'exclusions':arr(string()),'enabled':{'type':'boolean'},'source_sha256':nullable(string(pattern='^[0-9a-f]{64}$'))})
schemas['RuleRegistry']=obj({'version':string(),'rules':arr(ref('Rule'))})
schemas['ReviewInput']=obj({'decision':enum('unreviewed','confirmed','dismissed','uncertain'),'note':string(maxLength=2000)})
schemas['Review']=obj({'event_id':string(),'decision':enum('unreviewed','confirmed','dismissed','uncertain'),'note':string(maxLength=2000),'updated_at':nullable(string(format='date-time'))})
schemas['UiEvent']=obj({'event_id':string(),'jury_violation_index':{'type':'integer','minimum':0},'type':string(),'timecode_sec':number(minimum=0),'context_start_sec':number(minimum=0),'context_end_sec':number(minimum=0),'observation':string(),'rationale':string(),'limitations':arr(string()),'counterevidence':arr(string()),'rule_ids':arr(string(),minItems=1),'evidence_frames':arr(ref('EvidenceFrame'),minItems=1,maxItems=3),'review':ref('Review')})
schemas['CoverageSegment']=obj({'start_sec':number(minimum=0),'end_sec':number(minimum=0),'state':enum('assessed','limited','unassessed'),'reason':nullable(string())})
schemas['TimeMapSegment']=obj({'source_start_sec':number(minimum=0),'source_end_sec':number(minimum=0),'preview_start_sec':number(minimum=0),'preview_end_sec':number(minimum=0)})
schemas['ReviewCue']=obj({'cue_id':string(),'timecode_sec':number(minimum=0),'reason':string(),'limitations':arr(string()),'evidence_frames':arr(ref('EvidenceFrame'),minItems=1,maxItems=3)})
schemas['CaseSummary']=obj({'job_id':string(),'filename':string(),'created_at':string(format='date-time'),'status':enum('processing','done','failed'),'verdict':nullable(enum('violation','no_violation'))})
schemas['CaseList']=obj({'items':arr(ref('CaseSummary'))})
schemas['CaseDetail']=obj({'job_id':string(),'filename':string(),'created_at':string(format='date-time'),'status':enum('processing','done','failed'),'stage':enum('queued','decoding','screening','verifying','packaging','complete','failed'),'progress_percent':nullable(number(minimum=0,maximum=100)),'elapsed_sec':number(minimum=0),'duration_sec':nullable(number(minimum=0)),'model_result':nullable({'oneOf':[ref('DonePositive'),ref('DoneNegative')]}),'error':nullable(obj({'code':string(),'message':string()})),'events':arr(ref('UiEvent')),'coverage':arr(ref('CoverageSegment')),'media_ready':{'type':'boolean'},'time_map':arr(ref('TimeMapSegment')),'rule_registry_version':string(),'model_version':string(),'input_sha256':nullable(string(pattern='^[0-9a-f]{64}$')),'is_synthetic':{'type':'boolean'}})
schemas['CaseDetail']['properties'].update({'rules':arr(ref('Rule')),'review_cues':arr(ref('ReviewCue'))})
schemas['CaseDetail']['required']+=['rules','review_cues']
schemas['HealthLive']=obj({'status':{'const':'ok','type':'string'}})
schemas['HealthReady']=obj({'ready':{'type':'boolean'},'mode':enum('offline','server'),'contract_version':string()})

def response(schema, description='Success'):
    return {'description':description,'content':{'application/json':{'schema':schema}}}
errors={'401':response(ref('Error'),'Missing or invalid API key'),'404':response(ref('Error'),'Not found'),'422':response(ref('Error'),'Invalid request')}
def operation(opid, schema, params=None, body=None, status='200', auth=True):
    o={'operationId':opid,'responses':{status:response(schema),**(errors if auth else {})},'security':[{'ApiKeyAuth':[]}] if auth else []}
    if params: o['parameters']=params
    if body: o['requestBody']=body
    return o
job={'name':'job_id','in':'path','required':True,'schema':string()}
event={'name':'event_id','in':'path','required':True,'schema':string()}
paths={
 '/api/v1/analyze':{'post':operation('analyzeVideo',ref('UploadAccepted'),body={'required':True,'content':{'multipart/form-data':{'schema':obj({'file':string(format='binary')})}}},status='202')},
 '/api/v1/jobs/{job_id}':{'get':operation('getJuryJob',ref('JuryResult'),[job])},
 '/api/ui/cases':{'get':operation('listCases',ref('CaseList'))},
 '/api/ui/cases/{job_id}':{'get':operation('getCase',ref('CaseDetail'),[job]),'delete':operation('deleteCase',obj({'deleted':{'const':True,'type':'boolean'}}),[job])},
 '/api/ui/cases/{job_id}/reviews/{event_id}':{'put':operation('saveReview',ref('Review'),[job,event],body={'required':True,'content':{'application/json':{'schema':ref('ReviewInput')}}})},
 '/api/ui/rules':{'get':operation('getRuleRegistry',ref('RuleRegistry'))},
 '/health/live':{'get':operation('getLiveness',ref('HealthLive'),auth=False)},
 '/health/ready':{'get':operation('getReadiness',ref('HealthReady'),auth=False)}
}
paths['/api/v1/analyze']['post']['responses'].update({'413':response(ref('Error'),'Upload exceeds configured limit'),'415':response(ref('Error'),'Unsupported media'),'429':response(ref('Error'),'Queue cannot admit request within its budget; Retry-After header supplied'),'503':response(ref('Error'),'Worker/model unavailable')})
paths['/health/ready']['get']['responses']['503']=response(ref('HealthReady'),'Not ready')
for suffix,mime in [('media','video/mp4'),('bundle','application/zip')]:
    op=operation('getCase'+suffix.title(),string(format='binary'),[job])
    op['responses']['200']={'description':'Binary download','content':{mime:{'schema':string(format='binary')}}}
    op['responses']['409']=response(ref('Error'),'Artifact is not ready')
    paths[f'/api/ui/cases/{{job_id}}/{suffix}']={'get':op}
spec={'openapi':'3.1.0','info':{'title':'CashProof integration contract','version':'1.0.0','description':'Frozen handoff contract. Jury responses stay minimal. Synthetic fixtures never constitute model evaluation.'},'servers':[{'url':'/'}],'components':{'securitySchemes':{'ApiKeyAuth':{'type':'apiKey','in':'header','name':'X-API-Key'}},'schemas':schemas},'paths':paths}
(ROOT/'openapi.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2),encoding='utf-8')
launch=obj({'contract_version':{'const':'1.0.0','type':'string'},'executable':string(minLength=1),'args_prefix':arr(string()),'cwd':string(minLength=1),'env':{'type':'object','additionalProperties':string()}})
launch['$schema']='https://json-schema.org/draft/2020-12/schema'
(ROOT/'desktop-launch.schema.json').write_text(json.dumps(launch,indent=2),encoding='utf-8')

img=Image.new('RGB',(232,424),'#172233');d=ImageDraw.Draw(img)
d.rectangle((35,160,196,290),outline='#A99AFF',width=4)
d.text((36,80),'SYNTHETIC FIXTURE',fill='white')
d.text((48,330),'NO REAL FOOTAGE',fill='white')
buf=io.BytesIO();img.save(buf,format='JPEG',quality=80)
b64=base64.b64encode(buf.getvalue()).decode()
frame=lambda t:{'timestamp_sec':t,'image_base64':b64}
positive={'job_id':'synthetic-positive','status':'done','verdict':'violation','violations':[{'type':'Synthetic event A','timecode_sec':12.4,'description':'Synthetic integration fixture. This is not a finding about a person or a legal violation.','evidence_frames':[frame(11.4),frame(12.4),frame(13.4)]},{'type':'Synthetic event B','timecode_sec':21.0,'description':'Second synthetic event to exercise navigation and multi-event responses.','evidence_frames':[frame(21.0)]}]}
negative={'job_id':'synthetic-negative','status':'done','verdict':'no_violation','violations':[]}
processing={'job_id':'synthetic-processing','status':'processing'}
failed={'job_id':'synthetic-failed','status':'failed','error':{'code':'DECODE_FAILED','message':'Synthetic failure fixture.'}}
detail={'job_id':positive['job_id'],'filename':'synthetic-fixture.mov','created_at':'2026-10-17T06:00:00Z','status':'done','stage':'complete','progress_percent':100,'elapsed_sec':18,'duration_sec':30,'model_result':positive,'error':None,'events':[],'coverage':[{'start_sec':0,'end_sec':18,'state':'assessed','reason':None},{'start_sec':18,'end_sec':20,'state':'limited','reason':'Synthetic visibility limit'},{'start_sec':20,'end_sec':30,'state':'assessed','reason':None}],'media_ready':False,'time_map':[],'rule_registry_version':'synthetic-1','model_version':'synthetic-fixture-no-model','input_sha256':None,'is_synthetic':True}
for i,v in enumerate(positive['violations']):
    detail['events'].append({'event_id':f'synthetic-event-{i+1}','jury_violation_index':i,'type':v['type'],'timecode_sec':v['timecode_sec'],'context_start_sec':max(0,v['timecode_sec']-3),'context_end_sec':min(30,v['timecode_sec']+3),'observation':'Synthetic geometric scene for UI testing.','rationale':'No inference or legal conclusion was performed.','limitations':['Synthetic fixture only'],'counterevidence':[],'rule_ids':['SYNTHETIC_ONLY'],'evidence_frames':v['evidence_frames'],'review':{'event_id':f'synthetic-event-{i+1}','decision':'unreviewed','note':'','updated_at':None}})
rules={'version':'synthetic-1','rules':[{'rule_id':'SYNTHETIC_ONLY','display_name':'Synthetic fixture rule','document_title':'Integration fixture only','source_url':'https://example.invalid/synthetic','clause':'Not applicable','revision':'synthetic','effective_date':None,'applicability':'UI development only','exclusions':['Never use in production inference'],'enabled':False,'source_sha256':None}]}
detail['rules']=rules['rules'];detail['review_cues']=[]
fixtures=ROOT/'fixtures';fixtures.mkdir(exist_ok=True)
for name,data in [('jury-positive',positive),('jury-negative',negative),('jury-processing',processing),('jury-failed',failed),('ui-positive',detail),('rules',rules)]:
    (fixtures/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
for name,result in [('negative',negative),('processing',processing),('failed',failed)]:
    detail_copy={**detail,'job_id':result['job_id'],'status':result['status'],'stage':{'negative':'complete','processing':'screening','failed':'failed'}[name],'progress_percent':100 if name=='negative' else None,'model_result':result if name=='negative' else None,'error':result.get('error'),'events':[],'rules':[],'coverage':[],'duration_sec':30 if name=='negative' else None}
    (fixtures/('ui-'+name+'.json')).write_text(json.dumps(detail_copy,ensure_ascii=False,indent=2),encoding='utf-8')
print('Wrote OpenAPI 1.0.0 and 9 synthetic fixtures.')
