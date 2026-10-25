from __future__ import annotations
import json
import pytest
from aura.infrastructure.llm.nebius import NebiusAuthenticationError,NebiusPlannerProvider,NebiusProviderError,NebiusResponseError,NebiusTimeoutError
from aura.planner.live import LivePlanner
from aura.planner.schemas import ProjectRequest

KEY="secret-test-key"
class Response:
 def __init__(self,status=200,data=None,headers=None,text=""):
  self.status_code=status;self._data=data;self.headers=headers or {};self.text=text
 def json(self):return self._data
class Session:
 def __init__(self,*responses):self.responses=list(responses);self.calls=[]
 def post(self,url,**kwargs):self.calls.append((url,kwargs));value=self.responses.pop(0);return value() if callable(value) else value
def envelope(text,finish="stop",usage=None,refusal=None):return {"model":"nvidia/nemotron-test","choices":[{"finish_reason":finish,"message":{"content":text,"refusal":refusal}}],"usage":usage or {}}
def provider(*responses,**kwargs):session=Session(*responses);return NebiusPlannerProvider(KEY,"https://example.test/v1/","nvidia/nemotron-test",session=session,**kwargs),session

def test_nebius_request_disables_reasoning_and_sends_schema():
 nebius,session=provider(Response(data=envelope('{"ok":true}')))
 nebius.generate_structured([{"role":"user","content":"plan"}],system_prompt="bounded",response_schema={"type":"object"})
 url,request=session.calls[0];body=request["json"]
 assert url=="https://example.test/v1/chat/completions" and request["headers"]["Authorization"]==f"Bearer {KEY}"
 assert body["chat_template_kwargs"]=={"enable_thinking":False}
 assert body["response_format"]["json_schema"]["schema"]=={"type":"object"}
 assert body["messages"][0]=={"role":"system","content":"bounded"}

def test_nebius_usage_and_diagnostics_are_normalized():
 nebius,_=provider(Response(data=envelope('{"ok":true}',usage={"prompt_tokens":10,"completion_tokens":4,"total_tokens":14})))
 result=nebius.generate_structured([{"role":"user","content":"x"}])
 assert (result.input_tokens,result.output_tokens,result.total_tokens,result.model)==(10,4,14,"nvidia/nemotron-test")
 assert nebius.get_diagnostics()["backend"]=="nebius" and KEY not in json.dumps(nebius.get_diagnostics())

def test_nebius_transient_retry_is_bounded():
 delays=[];nebius,session=provider(Response(429,headers={"Retry-After":"0"}),Response(data=envelope('{"ok":true}')),max_retries=1,sleep=delays.append)
 assert nebius.generate([{"role":"user","content":"x"}])=='{"ok":true}' and len(session.calls)==2
 nebius,session=provider(Response(503),Response(503),max_retries=1,sleep=delays.append)
 with pytest.raises(NebiusProviderError):nebius.generate([{"role":"user","content":"x"}])
 assert len(session.calls)==2

def test_nebius_errors_are_classified_and_never_leak_the_key():
 cases=((Response(401,text=f"bad token {KEY}"),NebiusAuthenticationError),(Response(500,text=f"echo {KEY}"),NebiusProviderError),
        (Response(data={"bad":True}),NebiusResponseError),(Response(data=envelope("",finish="length")),NebiusResponseError),
        (Response(data=envelope("not json")),NebiusResponseError),(Response(data=envelope("{}",refusal="no")),NebiusResponseError))
 for response,error in cases:
  nebius,_=provider(response,max_retries=0)
  with pytest.raises(error) as caught:nebius.generate([{"role":"user","content":"x"}])
  assert KEY not in str(caught.value)
 class ReadTimeout(Exception):pass
 nebius,_=provider(lambda:(_ for _ in ()).throw(ReadTimeout()))
 with pytest.raises(NebiusTimeoutError):nebius.generate([{"role":"user","content":"x"}])
 with pytest.raises(ValueError):NebiusPlannerProvider("","https://example.test/v1","m")

def test_live_planner_uses_nebius_result_as_live_model():
 valid=json.dumps({"projectName":"Fan","objective":"Build a temperature controlled fan","requirements":["Low voltage"],"assumptions":[],"components":["controller","temperature sensor","fan","driver"]})
 nebius,_=provider(Response(data=envelope(valid,usage={"total_tokens":20})))
 outcome=LivePlanner(nebius,2).plan(ProjectRequest("Fan","Build a temperature controlled fan",("Low voltage",)))
 assert outcome.mode=="live_model" and outcome.provider_metadata["model"]=="nvidia/nemotron-test" and outcome.provider_metadata["provider"]=="nebius"

def test_workspace_selects_nebius_provider_from_settings(monkeypatch):
 from dataclasses import replace
 import aura.app.config as config
 from aura.workspace.server import WorkspaceApplication
 base=config.Settings()  # Settings reads env at import time, so patch the instance instead of env vars.
 monkeypatch.setattr(config,"Settings",lambda:replace(base,planner_provider="nebius",nebius_api_key=KEY,nebius_model="nvidia/nemotron-test"))
 selected=WorkspaceApplication(storage_mode="memory")._default_provider()
 assert isinstance(selected,NebiusPlannerProvider) and selected.model=="nvidia/nemotron-test"
