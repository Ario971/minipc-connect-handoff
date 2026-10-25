using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Threading;

namespace MiniPCConnect {
    public sealed class ProfileRecord {
        public string Harness {get;set;}
        public string Gateway {get;set;}
        public string Model {get;set;}
        public string UserId {get;set;}
        public string Alias {get;set;}
        public string Expires {get;set;}
        public string BinaryPath {get;set;}
        public bool Ready {get;set;}
        public double SmokeSeconds {get;set;}
    }
    public static class Client {
        public static string Quote(string value) {
            StringBuilder result=new StringBuilder("\"");
            int slashes=0;
            foreach(char character in value) {
                if(character=='\\') {slashes++; continue;}
                result.Append('\\',character=='"'?slashes*2+1:slashes);
                result.Append(character); slashes=0;
            }
            result.Append('\\',slashes*2); result.Append('"');
            return result.ToString();
        }
        public static void RequireEmptyProfile(string path) {
            if(Directory.Exists(path)) throw new IOException("Existing profile was not overwritten.");
        }
        static Dictionary<string,object> Map(params object[] values) {
            var d=new Dictionary<string,object>(); for(int i=0;i<values.Length;i+=2) d.Add((string)values[i],values[i+1]); return d;
        }
        public static ProcessStartInfo StartInfo(Deployment d,string kind,string profile,string key,string workspace,bool smoke) {
            ProcessStartInfo p=new ProcessStartInfo {UseShellExecute=false,WorkingDirectory=workspace,CreateNoWindow=smoke,
                RedirectStandardOutput=smoke,RedirectStandardError=smoke,RedirectStandardInput=smoke};
            var names=new List<string>(); foreach(string name in p.EnvironmentVariables.Keys) names.Add(name);
            foreach(string name in names) {
                string upper=name.ToUpperInvariant();
                if(upper.StartsWith("ANTHROPIC_") || upper.StartsWith("CLAUDE_") || upper.StartsWith("OPENCODE_") ||
                   upper.StartsWith("OPENAI_") || upper.StartsWith("AWS_") || upper.StartsWith("AZURE_") || upper.StartsWith("GOOGLE_") ||
                   upper.StartsWith("GEMINI_") || upper.StartsWith("OTEL_") || upper.Contains("API_KEY") || upper.EndsWith("_TOKEN") ||
                   upper.EndsWith("_SECRET") || upper=="NODE_TLS_REJECT_UNAUTHORIZED" || upper=="SSLKEYLOGFILE" ||
                   upper=="HTTP_PROXY" || upper=="HTTPS_PROXY" || upper=="ALL_PROXY") p.EnvironmentVariables.Remove(name);
            }
            foreach(var pair in new Dictionary<string,string>{{"HOME","home"},{"USERPROFILE","home"},{"XDG_CONFIG_HOME","config"},
                {"XDG_DATA_HOME","data"},{"XDG_CACHE_HOME","cache"},{"XDG_STATE_HOME","state"}}) {
                string path=Path.Combine(profile,pair.Value); Directory.CreateDirectory(path); p.EnvironmentVariables[pair.Key]=path;
            }
            p.EnvironmentVariables["NODE_EXTRA_CA_CERTS"]=d.CertificatePath;
            p.EnvironmentVariables["SSL_CERT_FILE"]=d.CertificatePath;
            p.EnvironmentVariables["NO_PROXY"]=new Uri(d.BaseUrl).Host+",localhost,127.0.0.1";
            p.EnvironmentVariables["DO_NOT_TRACK"]="1"; p.EnvironmentVariables["OTEL_SDK_DISABLED"]="true";
            if(kind=="opencode") {
                foreach(string suffix in new[]{"AUTOUPDATE","DEFAULT_PLUGINS","PROJECT_CONFIG","EXTERNAL_SKILLS","CLAUDE_CODE","MODELS_FETCH","LSP_DOWNLOAD","SHARE"})
                    p.EnvironmentVariables["OPENCODE_DISABLE_"+suffix]="true";
                p.EnvironmentVariables["OPENCODE_TEST_HOME"]=p.EnvironmentVariables["HOME"];
                p.EnvironmentVariables["OPENCODE_CONFIG_DIR"]=Path.Combine(profile,"config","opencode");
                p.EnvironmentVariables["MINIPC_PILOT_API_KEY"]=key;
                object permission=smoke ? (object)Map("*","deny","read",Map("*","deny","connection-check.txt","allow","*/connection-check.txt","allow"))
                    : Map("*","ask","read","allow","glob","allow","grep","allow","external_directory","ask");
                var config=Map("$schema","https://opencode.ai/config.json","enabled_providers",new[]{"minipc"},"model","minipc/"+d.Model,
                    "small_model","minipc/"+d.Model,"share","disabled","autoupdate",false,"snapshot",false,"plugin",new string[0],
                    "mcp",Map(),"instructions",new string[0],"permission",permission,
                    "provider",Map("minipc",Map("npm","@ai-sdk/openai-compatible","name",d.SiteName,
                    "options",Map("baseURL",d.BaseUrl+"/v1","apiKey","{env:MINIPC_PILOT_API_KEY}","timeout",150000),
                    "models",Map(d.Model,Map("name","MiniPC local model","toolcall",true,"limit",Map("context",d.ContextTokens,"output",d.OutputTokens),
                    "cost",Map("input",0,"output",0),"options",Map("temperature",0))))));
                p.EnvironmentVariables["OPENCODE_CONFIG_CONTENT"]=Deployment.Json.Serialize(config);
                p.Arguments=Quote(workspace)+" --pure --model "+Quote("minipc/"+d.Model);
            } else if(kind=="claude") {
                p.EnvironmentVariables["CLAUDE_CONFIG_DIR"]=Path.Combine(profile,"claude");
                Directory.CreateDirectory(p.EnvironmentVariables["CLAUDE_CONFIG_DIR"]);
                p.EnvironmentVariables["ANTHROPIC_BASE_URL"]=d.BaseUrl;
                p.EnvironmentVariables["ANTHROPIC_API_KEY"]=key;
                p.EnvironmentVariables["ANTHROPIC_MODEL"]=d.Model;
                foreach(string suffix in new[]{"HAIKU","SONNET","OPUS","FABLE"}) p.EnvironmentVariables["ANTHROPIC_DEFAULT_"+suffix+"_MODEL"]=d.Model;
                p.EnvironmentVariables["CLAUDE_CODE_SUBAGENT_MODEL"]=d.Model;
                p.EnvironmentVariables["CLAUDE_CODE_MAX_CONTEXT_TOKENS"]=d.ContextTokens.ToString();
                p.EnvironmentVariables["CLAUDE_CODE_MAX_OUTPUT_TOKENS"]=d.OutputTokens.ToString();
                p.EnvironmentVariables["MAX_THINKING_TOKENS"]="0";
                p.EnvironmentVariables["CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS"]="1";
                p.EnvironmentVariables["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"]="1";
                p.EnvironmentVariables["DISABLE_AUTOUPDATER"]="1";
                p.EnvironmentVariables["CLAUDE_CODE_MAX_RETRIES"]="0";
                p.EnvironmentVariables["API_TIMEOUT_MS"]="150000";
                p.Arguments="--bare --model "+Quote(d.Model)+" --setting-sources user --strict-mcp-config --permission-mode manual --no-chrome";
            } else throw new ArgumentException("Unknown harness");
            return p;
        }
        public static Dictionary<string,object> RunReadCheck(Deployment d,string kind,string profile,string binary,string key,CancellationToken cancel) {
            string workspace=Path.Combine(profile,"checks",Guid.NewGuid().ToString("N")); Directory.CreateDirectory(workspace);
            string marker="MINIPC_CONNECT_"+Guid.NewGuid().ToString("N");
            File.WriteAllText(Path.Combine(workspace,"connection-check.txt"),marker,Encoding.UTF8);
            ProcessStartInfo info=StartInfo(d,kind,profile,key,workspace,true); info.FileName=binary;
            string prompt="Read connection-check.txt using the Read tool. Reply with its exact content. Do not use other tools or change files.";
            if(kind=="opencode") info.Arguments="run --pure --model "+Quote("minipc/"+d.Model)+" --format json --dir "+Quote(workspace)+" "+Quote(prompt);
            else info.Arguments+=" -p "+Quote(prompt)+" --allowedTools Read --output-format stream-json --verbose --no-session-persistence";
            StringBuilder output=new StringBuilder(),error=new StringBuilder(); object gate=new object();
            Stopwatch clock=Stopwatch.StartNew(); bool timeout=false;
            using(Process process=new Process {StartInfo=info}) {
                process.OutputDataReceived+=(s,e)=>{if(e.Data!=null) lock(gate) {if(output.Length<1024*1024) output.AppendLine(e.Data);}};
                process.ErrorDataReceived+=(s,e)=>{if(e.Data!=null) lock(gate) {if(error.Length<64*1024) error.AppendLine(e.Data);}};
                process.Start(); process.StandardInput.Close(); process.BeginOutputReadLine(); process.BeginErrorReadLine();
                while(!process.WaitForExit(250)) {
                    if(clock.Elapsed.TotalSeconds>150 || cancel.IsCancellationRequested) {
                        timeout=true;
                        using(Process killer=Process.Start(new ProcessStartInfo("taskkill.exe","/PID "+process.Id+" /T /F") {UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true})) killer.WaitForExit(10000);
                        break;
                    }
                }
                if(!process.WaitForExit(10000)) throw new TimeoutException("The owned test process did not stop.");
                process.WaitForExit();
                bool read=false,reply=false;
                foreach(string line in output.ToString().Split('\n')) {
                    Dictionary<string,object> ev;
                    try {ev=Deployment.Json.Deserialize<Dictionary<string,object>>(line);} catch {continue;}
                    if(ev==null || !ev.ContainsKey("type")) continue;
                    string type=Convert.ToString(ev["type"]);
                    if(kind=="claude") {
                        if(type=="assistant" && ev.ContainsKey("message")) {
                            var message=(Dictionary<string,object>)ev["message"];
                            foreach(Dictionary<string,object> block in (IEnumerable)message["content"])
                                if(Convert.ToString(block["type"])=="tool_use" && Convert.ToString(block["name"])=="Read") read=true;
                        }
                        if(type=="result" && !Convert.ToBoolean(ev["is_error"]) && Convert.ToString(ev["result"]).Contains(marker)) reply=true;
                    } else if(ev.ContainsKey("part")) {
                        var part=(Dictionary<string,object>)ev["part"];
                        if(type=="tool_use" && part.ContainsKey("tool") && Convert.ToString(part["tool"])=="read") {
                            var state=(Dictionary<string,object>)part["state"];
                            read=Convert.ToString(state["status"])=="completed" && state.ContainsKey("output") && Convert.ToString(state["output"]).Contains(marker);
                        }
                        if(type=="text" && Convert.ToString(part["text"]).Contains(marker)) reply=true;
                    }
                }
                var report=Map("harness",kind,"read_tool",read,"correct_reply",reply,"timed_out",timeout,"exit_code",process.ExitCode,
                    "seconds",Math.Round(clock.Elapsed.TotalSeconds,3),"passed",!timeout && process.ExitCode==0 && read && reply);
                File.WriteAllText(Path.Combine(workspace,"report.json"),Deployment.Json.Serialize(report),Encoding.UTF8);
                if(!(bool)report["passed"]) {
                    string diagnostic=(output.ToString()+error.ToString()).Replace(key,"[REDACTED]");
                    File.WriteAllText(Path.Combine(workspace,"failure.txt"),diagnostic,Encoding.UTF8);
                    throw new InvalidOperationException(kind+" read-tool test did not pass within the 150-second limit. This installation is not Ready; the new key will be revoked. Details remain only in the private test folder.");
                }
                return report;
            }
        }
        public static ProfileRecord Install(Deployment d,Gateway gateway,string kind,string root,Action<string> progress,CancellationToken cancel) {
            string final=Path.Combine(root,"profiles",kind);
            if(Directory.Exists(final)) {
                ProfileRecord saved=Deployment.Json.Deserialize<ProfileRecord>(File.ReadAllText(Path.Combine(final,"profile.json")));
                if(saved.UserId!=gateway.UserId || saved.Gateway!=d.BaseUrl || saved.Model!=d.Model || !saved.Ready)
                    throw new IOException("A different or unfinished profile exists; it was not overwritten.");
                Security.RequireHash(saved.BinaryPath,(kind=="opencode"?d.OpenCode:d.Claude).BinarySHA256);
                gateway.VerifyKey(ReadKey(final)); progress(kind+": پروفایل موجود معتبر است؛ تغییری نکرد"); return saved;
            }
            string binary=Artifacts.Ensure(d,kind,root,progress,cancel); cancel.ThrowIfCancellationRequested();
            string stage=Path.Combine(root,"private","setup-"+Guid.NewGuid().ToString("N")); Security.PrivateDirectory(stage);
            string alias=d.SiteId+"-"+kind+"-"+Guid.NewGuid().ToString("N").Substring(0,12), key=null;
            try {
                progress(kind+": ساخت کلید اختصاصی و محدود");
                var issued=gateway.CreateKey(alias); key=Convert.ToString(issued["key"]);
                gateway.VerifyKey(key); cancel.ThrowIfCancellationRequested();
                File.WriteAllBytes(Path.Combine(stage,"key.dpapi"),Security.Protect(Encoding.UTF8.GetBytes(key)));
                progress(kind+": آزمون واقعی خواندن فایل — حداکثر ۱۵۰ ثانیه");
                var check=RunReadCheck(d,kind,stage,binary,key,cancel);
                var record=new ProfileRecord {Harness=kind,Gateway=d.BaseUrl,Model=d.Model,UserId=gateway.UserId,Alias=alias,
                    Expires=Convert.ToString(issued["expires"]),BinaryPath=binary,Ready=true,SmokeSeconds=Convert.ToDouble(check["seconds"])};
                File.WriteAllText(Path.Combine(stage,"profile.json"),Deployment.Json.Serialize(record),Encoding.UTF8);
                Directory.CreateDirectory(Path.GetDirectoryName(final)); RequireEmptyProfile(final); Directory.Move(stage,final);
                progress(kind+": آماده — کلید و پروفایل مستقل"); return record;
            } catch {
                if(key!=null) {
                    try {gateway.Revoke(key);} catch {
                        throw new InvalidOperationException("Setup failed and key revocation needs owner attention. Key alias: "+alias);
                    }
                }
                throw;
            }
        }
        public static void RequireOwner(Deployment d,string profile,string owner) {
            if(!Directory.Exists(profile)) return;
            if((File.GetAttributes(profile)&FileAttributes.ReparsePoint)!=0) throw new IOException("Profile cannot be a link or junction.");
            var saved=Deployment.Json.Deserialize<ProfileRecord>(File.ReadAllText(Path.Combine(profile,"profile.json")));
            if(saved.UserId!=owner || saved.Gateway!=d.BaseUrl || saved.Model!=d.Model)
                throw new IOException("A different account or gateway owns this profile; it was not changed.");
        }
        public static ProfileRecord PrepareIssued(Deployment d,string root,string stage,string owner,Dictionary<string,object> issued,Action<string,string> progress,CancellationToken cancel) {
            string kind=Convert.ToString(issued["harness"]),key=Convert.ToString(issued["key"]);
            if(kind!="opencode" && kind!="claude") throw new InvalidDataException("Unknown harness.");
            RequireOwner(d,Path.Combine(root,"profiles",kind),owner);
            Security.PrivateDirectory(stage);
            progress("downloading",kind);
            string binary=Artifacts.Ensure(d,kind,root,s=>{},cancel);
            cancel.ThrowIfCancellationRequested(); progress("verifying",kind);
            using(var gateway=new Gateway(d)) gateway.VerifyKey(key);
            File.WriteAllBytes(Path.Combine(stage,"key.dpapi"),Security.Protect(Encoding.UTF8.GetBytes(key)));
            progress("testing",kind);
            var check=RunReadCheck(d,kind,stage,binary,key,cancel);
            var record=new ProfileRecord {Harness=kind,Gateway=d.BaseUrl,Model=d.Model,UserId=owner,
                Alias=Convert.ToString(issued["key_alias"]),Expires=Convert.ToString(issued["expires"]),BinaryPath=binary,
                Ready=false,SmokeSeconds=Convert.ToDouble(check["seconds"])};
            File.WriteAllText(Path.Combine(stage,"profile.json"),Deployment.Json.Serialize(record),Encoding.UTF8);
            return record;
        }
        public static string ReadKey(string profile) {return Encoding.UTF8.GetString(Security.Unprotect(File.ReadAllBytes(Path.Combine(profile,"key.dpapi"))));}
        public static void Launch(Deployment d,string kind,string root,string project) {
            string profile=Path.Combine(root,"profiles",kind);
            var saved=Deployment.Json.Deserialize<ProfileRecord>(File.ReadAllText(Path.Combine(profile,"profile.json")));
            if(!saved.Ready || saved.Gateway!=d.BaseUrl || saved.Model!=d.Model) throw new InvalidOperationException("Profile is not ready for this gateway.");
            Security.RequireHash(saved.BinaryPath,(kind=="opencode"?d.OpenCode:d.Claude).BinarySHA256);
            string key=ReadKey(profile); using(Gateway gateway=new Gateway(d)) gateway.VerifyKey(key);
            if(!Directory.Exists(project)) throw new DirectoryNotFoundException("Choose an existing project folder.");
            ProcessStartInfo info=StartInfo(d,kind,profile,key,project,false); info.FileName=saved.BinaryPath; Process.Start(info);
        }
    }
}
