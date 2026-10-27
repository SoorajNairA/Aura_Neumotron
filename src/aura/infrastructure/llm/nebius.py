from __future__ import annotations

import json
import time
from typing import Any,Callable

from .provider import ModelGenerationResult

class NebiusProviderError(RuntimeError): pass
class NebiusAuthenticationError(NebiusProviderError): pass
class NebiusTimeoutError(NebiusProviderError): pass
class NebiusResponseError(NebiusProviderError): pass

class NebiusPlannerProvider:
    """OpenAI-compatible chat adapter (Nebius Token Factory by default; also OpenAI-style endpoints and Ollama /v1) with normalized results."""
    TRANSIENT={408,429,500,502,503,504}

    def __init__(self,api_key:str,base_url:str,model:str,timeout_seconds:float=25,max_retries:int=1,*,session:Any|None=None,sleep:Callable[[float],None]=time.sleep,provider_name:str="nebius",require_key:bool=True)->None:
        self.provider_name=provider_name;self._require_key=require_key;self._label="Nebius" if provider_name=="nebius" else provider_name;self._api_key=api_key.strip();self.base_url=base_url.strip().rstrip("/");self.model=model.strip();self.timeout_seconds=timeout_seconds;self.max_retries=max(0,min(max_retries,2));self._session=session;self._sleep=sleep;self.last_result:ModelGenerationResult|None=None
        if not all(((self._api_key or not require_key),self.base_url,self.model)):
            raise ValueError("NEBIUS_API_KEY, NEBIUS_BASE_URL, and NEBIUS_MODEL are required" if provider_name=="nebius" else f"{self._label} requires an API key, base URL and model")

    @property
    def endpoint(self)->str: return f"{self.base_url}/chat/completions"

    def _http(self):
        if self._session is None:
            import requests
            self._session=requests.Session()
        return self._session

    def request_payload(self,messages:list[dict[str,str]],system_prompt:str|None,max_tokens:int,response_schema:dict[str,Any]|None=None)->dict[str,Any]:
        chat=([{"role":"system","content":system_prompt}] if system_prompt else [])+[{"role":item["role"],"content":item["content"]} for item in messages]
        payload:dict[str,Any]={"model":self.model,"messages":chat,"max_tokens":max_tokens,"temperature":0.1}
        # Nemotron reasons by default; reasoning consumed the whole token budget and left the answer empty. Other models reject or ignore the extension.
        if "nemotron" in self.model.lower(): payload["chat_template_kwargs"]={"enable_thinking":False}
        payload["response_format"]={"type":"json_schema","json_schema":{"name":"aura_response","schema":response_schema}} if response_schema else {"type":"json_object"}
        return payload

    def generate_structured(self,messages:list[dict[str,str]],*,system_prompt:str|None=None,max_tokens:int=1200,response_schema:dict[str,Any]|None=None)->ModelGenerationResult:
        payload=self.request_payload(messages,system_prompt,max_tokens,response_schema);session=self._http();response=None
        headers={"Authorization":f"Bearer {self._api_key}"} if self._api_key else {}
        for attempt in range(self.max_retries+1):
            try: response=session.post(self.endpoint,json=payload,headers=headers,timeout=self.timeout_seconds)
            except Exception as exc:
                if exc.__class__.__name__.lower().endswith("timeout"): raise NebiusTimeoutError(f"{self._label} request exceeded {self.timeout_seconds:g}s") from None
                if attempt<self.max_retries:self._sleep(.25*(attempt+1));continue
                # from None: transport exceptions may carry request headers, including the key.
                raise NebiusProviderError(f"{self._label} network request failed: {exc.__class__.__name__}") from None
            if response.status_code in self.TRANSIENT and attempt<self.max_retries:
                retry=float(response.headers.get("Retry-After",.25));self._sleep(min(max(retry,0),2));continue
            break
        assert response is not None
        if response.status_code in {401,403}: raise NebiusAuthenticationError(f"{self._label} API key was rejected ({response.status_code}); check NEBIUS_API_KEY and model access" if self.provider_name=="nebius" else f"{self._label} API key was rejected ({response.status_code}); check the key and model access")
        if response.status_code>=400:
            body=response.text.replace(self._api_key,'***') if self._api_key else response.text
            raise NebiusProviderError(f"{self._label} request failed ({response.status_code}): {body[:300]}")
        try:data=response.json();choice=data["choices"][0];finish=choice.get("finish_reason") or "";text=choice["message"].get("content") or ""
        except Exception as exc: raise NebiusResponseError(f"{self._label} returned a malformed response envelope") from exc
        if choice["message"].get("refusal"): raise NebiusResponseError(f"{self.model} refused the request")
        try:json.loads(text)
        except Exception as exc: raise NebiusResponseError(f"{self.model} did not return valid structured JSON (finish: {finish or 'unknown'})") from exc
        usage=data.get("usage") or {}
        result=ModelGenerationResult(text,usage.get("prompt_tokens"),usage.get("completion_tokens"),usage.get("total_tokens"),data.get("model") or self.model,{"finishReason":finish,"provider":self.provider_name})
        self.last_result=result;return result

    def generate(self,messages:list[dict[str,str]],*,system_prompt:str|None=None,max_tokens:int=512)->str:
        return self.generate_structured(messages,system_prompt=system_prompt,max_tokens=max_tokens).text
    def stream_generate(self,*args,**kwargs): yield self.generate(*args,**kwargs)
    def is_available(self)->bool: return bool(self._api_key) or not self._require_key
    def get_diagnostics(self)->dict[str,Any]:
        return {"backend":self.provider_name,"baseUrl":self.base_url,"model":self.model,"structuredOutput":True,"streaming":False}
