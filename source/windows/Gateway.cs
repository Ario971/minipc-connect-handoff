using System;
using System.Text;
using System.Collections.Generic;
using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;

namespace MiniPCConnect {
    public sealed class Gateway : IDisposable {
        readonly Deployment deployment;
        readonly HttpClient http;
        string sessionKey;
        public string UserId {get;private set;}
        public string Email {get;private set;}
        public Gateway(Deployment d) {
            deployment=d;
            ServicePointManager.SecurityProtocol=SecurityProtocolType.Tls12;
            http=new HttpClient(new HttpClientHandler {AllowAutoRedirect=false,UseCookies=false}) {Timeout=TimeSpan.FromSeconds(25)};
        }
        public static Dictionary<string,object> KeyRequest(string userId,string alias,string model) {
            return new Dictionary<string,object> {{"user_id",userId},{"key_alias",alias},{"models",new[]{model}},
                {"key_type","llm_api"},{"duration","30d"},
                {"max_parallel_requests",1},{"rpm_limit",30},{"tpm_limit",60000}};
        }
        Dictionary<string,object> Call(string path,object body,string credential) {
            using(HttpRequestMessage request=new HttpRequestMessage(body==null?HttpMethod.Get:HttpMethod.Post,deployment.BaseUrl+path)) {
                if(credential!=null) request.Headers.Authorization=new AuthenticationHeaderValue("Bearer",credential);
                if(body!=null) request.Content=new StringContent(Deployment.Json.Serialize(body),Encoding.UTF8,"application/json");
                using(HttpResponseMessage response=http.SendAsync(request).GetAwaiter().GetResult()) {
                    if(!response.IsSuccessStatusCode) throw new InvalidOperationException("Gateway "+path+" returned HTTP "+(int)response.StatusCode+". Check account, permissions or connection; no cloud fallback was used.");
                    string text=response.Content.ReadAsStringAsync().GetAwaiter().GetResult();
                    return Deployment.Json.Deserialize<Dictionary<string,object>>(text);
                }
            }
        }
        public void Login(string username,string password) {
            var result=Call("/v2/login",new {username=username,password=password},null);
            string token=Convert.ToString(result["token"]);
            string[] parts=token.Split('.');
            if(parts.Length!=3) throw new InvalidOperationException("Unexpected gateway login response.");
            string encoded=parts[1].Replace('-','+').Replace('_','/');
            encoded=encoded.PadRight((encoded.Length+3)/4*4,'=');
            var claims=Deployment.Json.Deserialize<Dictionary<string,object>>(Encoding.UTF8.GetString(Convert.FromBase64String(encoded)));
            if(claims.ContainsKey("password_reset_required") && Convert.ToBoolean(claims["password_reset_required"]))
                throw new InvalidOperationException("First finish the required password change in the LiteLLM panel, then sign in here again.");
            // Claims are only a credential envelope; identity and role come from the authenticated API.
            sessionKey=Convert.ToString(claims["key"]);
            var identity=Call("/v2/user/info",null,sessionKey);
            UserId=Convert.ToString(identity["user_id"]); Email=Convert.ToString(identity["user_email"]);
            string role=Convert.ToString(identity["user_role"]);
            if(string.IsNullOrEmpty(UserId) || (role!="internal_user" && role!="proxy_admin"))
                throw new InvalidOperationException("This account cannot create its own client keys. Ask the owner for an Internal User invitation.");
        }
        public Dictionary<string,object> CreateKey(string alias) {
            if(sessionKey==null) throw new InvalidOperationException("Sign in first.");
            return Call("/key/generate",KeyRequest(UserId,alias,deployment.Model),sessionKey);
        }
        public void Revoke(string key) {Call("/key/delete",new {keys=new[]{key}},sessionKey);}
        public void VerifyKey(string key) {
            var result=Call("/v1/models",null,key);
            var entries=(System.Collections.IEnumerable)result["data"];
            int count=0;
            foreach(Dictionary<string,object> model in entries) {
                if(Convert.ToString(model["id"])!=deployment.Model) throw new InvalidOperationException("Unexpected model access on the client key.");
                count++;
            }
            if(count!=1) throw new InvalidOperationException("The expected model is unavailable.");
            using(HttpRequestMessage request=new HttpRequestMessage(HttpMethod.Get,deployment.BaseUrl+"/key/list")) {
                request.Headers.Authorization=new AuthenticationHeaderValue("Bearer",key);
                using(HttpResponseMessage response=http.SendAsync(request).GetAwaiter().GetResult())
                    if(response.StatusCode!=HttpStatusCode.Forbidden) throw new InvalidOperationException("Client key scope verification failed.");
            }
        }
        public void Dispose() {sessionKey=null; http.Dispose();}
    }
}
