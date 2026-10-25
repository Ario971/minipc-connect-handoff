using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Reflection;
using System.Text.RegularExpressions;
using System.Threading;

namespace MiniPCConnect {
    public static class AtomicFile {
        public static void Replace(string next,string destination) {
            string backup=destination+".atomic-backup";
            for(int attempt=0;;attempt++) {
                try {
                    if(File.Exists(destination)) File.Replace(next,destination,backup);else File.Move(next,destination);
                    return;
                } catch(IOException error) {
                    int code=error.HResult&0xffff;
                    if(attempt>=3 || !File.Exists(next) || (code!=32 && code!=33 && code!=1175)) throw;
                    Thread.Sleep(100*(attempt+1));
                }
            }
        }
        public static void Write(string path,string value) {
            string next=path+".new";File.WriteAllText(next,value,Encoding.UTF8);Replace(next,path);
        }
    }
    public sealed class CredentialChange {
        public string Stage {get;set;}
        public string Final {get;set;}
        public string Backup {get;set;}
        public bool Existed {get;set;}
        public static CredentialChange Prepare(string stage,string final,string backup) {
            var change=new CredentialChange {Stage=stage,Final=final,Backup=backup,Existed=Directory.Exists(final)};
            Security.PrivateDirectory(backup);
            if(change.Existed) foreach(string file in new[]{"key.dpapi","profile.json"}) File.Copy(Path.Combine(final,file),Path.Combine(backup,file),false);
            return change;
        }
        public void Promote() {
            Directory.CreateDirectory(Path.GetDirectoryName(Final));
            if(!Existed) {
                if(Directory.Exists(Stage)) Directory.Move(Stage,Final);
                else if(!File.Exists(Path.Combine(Final,"key.dpapi")) || !File.Exists(Path.Combine(Final,"profile.json"))) throw new IOException("Promoted profile is incomplete.");
                return;
            }
            foreach(string file in new[]{"key.dpapi","profile.json"}) {
                string temporary=Path.Combine(Final,file+".new");File.Copy(Path.Combine(Stage,file),temporary,true);
                AtomicFile.Replace(temporary,Path.Combine(Final,file));
            }
        }
        public void Rollback() {
            if(!Existed) {if(Directory.Exists(Final) && !Directory.Exists(Stage)) Directory.Move(Final,Stage);return;}
            foreach(string file in new[]{"key.dpapi","profile.json"}) File.Copy(Path.Combine(Backup,file),Path.Combine(Final,file),true);
        }
        public void MarkReady() {
            string path=Path.Combine(Final,"profile.json");
            var record=Deployment.Json.Deserialize<ProfileRecord>(File.ReadAllText(path));record.Ready=true;
            AtomicFile.Write(path,Deployment.Json.Serialize(record));
        }
    }
    public sealed class PairJournal {
        public string ProtectedToken {get;set;}
        public string Phase {get;set;}
        public List<CredentialChange> Changes {get;set;}
        public Dictionary<string,double> Receipts {get;set;}
    }
    public sealed class Portal : IDisposable {
        readonly Deployment deployment;
        readonly HttpClient http;
        public Portal(Deployment d) {
            deployment=d;ServicePointManager.SecurityProtocol=SecurityProtocolType.Tls12;
            http=new HttpClient(new HttpClientHandler {AllowAutoRedirect=false,UseCookies=false}) {Timeout=TimeSpan.FromSeconds(60),MaxResponseContentBufferSize=2*1024*1024};
        }
        public void Dispose() {http.Dispose();}
        public static string PairUrl(Deployment d,string code) {
            if(!Regex.IsMatch(code??"",@"^[A-Z2-9]{10}$")) throw new InvalidDataException("Invalid public pairing code.");
            return d.BaseUrl+"/connect/#pair="+code;
        }
        Dictionary<string,object> Call(string path,string token,object body=null) {
            using(var request=new HttpRequestMessage(body==null?HttpMethod.Get:HttpMethod.Post,deployment.BaseUrl+"/connect/api"+path)) {
                if(token!=null) request.Headers.Authorization=new AuthenticationHeaderValue("Bearer",token);
                if(body!=null) request.Content=new StringContent(Deployment.Json.Serialize(body),Encoding.UTF8,"application/json");
                using(var response=http.SendAsync(request).GetAwaiter().GetResult()) {
                    if(!response.IsSuccessStatusCode) throw new InvalidOperationException("Portal "+path+" returned HTTP "+(int)response.StatusCode+". No cloud fallback or TLS bypass was used.");
                    return Deployment.Json.Deserialize<Dictionary<string,object>>(response.Content.ReadAsStringAsync().GetAwaiter().GetResult());
                }
            }
        }
        static void Save(string path,PairJournal journal) {
            AtomicFile.Write(path,Deployment.Json.Serialize(journal));
        }
        static void RequireOwnedPaths(string root,PairJournal journal) {
            string privateRoot=Path.GetFullPath(Path.Combine(root,"private"))+Path.DirectorySeparatorChar;
            foreach(var change in journal.Changes) {
                string final=Path.GetFullPath(change.Final);
                if(final!=Path.Combine(root,"profiles","opencode") && final!=Path.Combine(root,"profiles","claude")) throw new IOException("Unexpected enrollment destination.");
                if(!Path.GetFullPath(change.Stage).StartsWith(privateRoot,StringComparison.OrdinalIgnoreCase) || !Path.GetFullPath(change.Backup).StartsWith(privateRoot,StringComparison.OrdinalIgnoreCase)) throw new IOException("Unexpected recovery path.");
            }
        }
        static void Finish(Deployment d,string root,PairJournal journal,string journalPath) {
            foreach(var change in journal.Changes) change.MarkReady();
            string exe=Path.Combine(root,"MiniPCConnect.exe"),source=Assembly.GetExecutingAssembly().Location;
            if(!string.Equals(exe,source,StringComparison.OrdinalIgnoreCase)) File.Copy(source,exe,true);
            foreach(string name in new[]{"pilot.json",d.CAFile}) {
                string from=Path.Combine(d.DirectoryPath,name),to=Path.Combine(root,name);
                if(!string.Equals(from,to,StringComparison.OrdinalIgnoreCase)) File.Copy(from,to,true);
            }
            Directory.CreateDirectory(Path.Combine(root,"workspace"));
            string shortcuts=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs),"MiniPC Connect - "+d.SiteId);
            bool acceptance=Path.GetFileName(root).StartsWith("minipc-connect-acceptance-",StringComparison.Ordinal);
            if(!acceptance) Directory.CreateDirectory(shortcuts);
            foreach(string kind in journal.Receipts.Keys) {
                string cmd="@echo off\r\n\""+exe+"\" --launch "+kind+"\r\n";
                File.WriteAllText(Path.Combine(root,"Start-"+kind+".cmd"),cmd,Encoding.Default);
                if(!acceptance) File.WriteAllText(Path.Combine(shortcuts,"Start-"+kind+".cmd"),cmd,Encoding.Default);
            }
            // Backups contain only already-revoked credentials; remove exact known files.
            foreach(var change in journal.Changes) foreach(string file in new[]{"key.dpapi","profile.json"}) {
                string backup=Path.Combine(change.Backup,file);if(File.Exists(backup)) File.Delete(backup);
            }
            File.Delete(journalPath);
        }
        public void Run(string root,bool browser,Action<string> progress,CancellationToken cancel) {
            if(!Security.IsTrusted(deployment)) throw new InvalidOperationException("The site certificate is not trusted. Ask the administrator to approve its fingerprint and install the public root; HTTPS verification remains enabled.");
            var info=Call("/info",null);
            if(Convert.ToString(info["SiteId"])!=deployment.SiteId || Convert.ToString(info["BaseUrl"])!=deployment.BaseUrl || Convert.ToString(info["Model"])!=deployment.Model || Convert.ToInt32(info["ContextTokens"])!=deployment.ContextTokens || Convert.ToInt32(info["OutputTokens"])!=deployment.OutputTokens)
                throw new InvalidDataException("This helper has a different or outdated site configuration. Download the current package from your portal.");
            Security.PrivateDirectory(root);Security.PrivateDirectory(Path.Combine(root,"private"));
            if((File.GetAttributes(root)&FileAttributes.ReparsePoint)!=0) throw new IOException("Installation root cannot be a junction.");
            using(var guard=new FileStream(Path.Combine(root,"enroll.lock"),FileMode.OpenOrCreate,FileAccess.ReadWrite,FileShare.None)) {
                string journalPath=Path.Combine(root,"private","pairing.json");
                if(File.Exists(journalPath)) {
                    var previous=Deployment.Json.Deserialize<PairJournal>(File.ReadAllText(journalPath));RequireOwnedPaths(root,previous);
                    string priorToken=Encoding.UTF8.GetString(Security.Unprotect(Convert.FromBase64String(previous.ProtectedToken)));
                    if(previous.Phase=="committing" || previous.Phase=="promoting") {
                        var status=Call("/poll",priorToken);
                        if(previous.Phase=="promoting" && Convert.ToString(status["status"])=="approved") {
                            foreach(var change in previous.Changes) change.Promote();
                            previous.Phase="committing";Save(journalPath,previous);
                        }
                        if(Convert.ToString(status["status"])=="approved") status=Call("/complete",priorToken,new {receipts=previous.Receipts});
                        if(Convert.ToString(status["status"])!="ready") throw new IOException("Previous setup outcome is uncertain. Keep recovery files and ask the administrator; existing keys were not replaced again.");
                        Finish(deployment,root,previous,journalPath);progress("READY");return;
                    }
                    foreach(var change in previous.Changes) change.Rollback();
                    try {Call("/fail",priorToken,new {reason="cancelled"});} catch { /* Server expiry cleanup owns unfinished keys. */ }
                    File.Delete(journalPath);
                }
                string deviceFile=Path.Combine(root,"device-id");
                string device=File.Exists(deviceFile)?File.ReadAllText(deviceFile).Trim():Guid.NewGuid().ToString("N");
                if(!Regex.IsMatch(device,@"^[a-f0-9]{32}$")) throw new IOException("Invalid local device identifier.");
                if(!File.Exists(deviceFile)) File.WriteAllText(deviceFile,device,Encoding.ASCII);
                var pair=Call("/pair/start",null,new {device_id=device,label=Environment.MachineName});
                string token=Convert.ToString(pair["device_token"]),url=PairUrl(deployment,Convert.ToString(pair["code"]));
                var journal=new PairJournal {ProtectedToken=Convert.ToBase64String(Security.Protect(Encoding.UTF8.GetBytes(token))),Phase="preparing",Changes=new List<CredentialChange>(),Receipts=new Dictionary<string,double>()};
                Save(journalPath,journal);progress(url);
                if(browser) Process.Start(new ProcessStartInfo(url) {UseShellExecute=true});
                try {
                    var clock=Stopwatch.StartNew();Dictionary<string,object> state;
                    do {
                        cancel.ThrowIfCancellationRequested();
                        if(clock.Elapsed.TotalMinutes>10) throw new TimeoutException("Browser approval expired. Run the helper again.");
                        state=Call("/poll",token);
                        if(Convert.ToString(state["status"])=="pending") cancel.WaitHandle.WaitOne(2000);
                    } while(Convert.ToString(state["status"])=="pending");
                    if(Convert.ToString(state["status"])!="approved") throw new IOException("Device setup was not approved.");
                    string owner=Convert.ToString(state["user_id"]);
                    foreach(Dictionary<string,object> issued in (IEnumerable)state["keys"]) {
                        string kind=Convert.ToString(issued["harness"]),stage=Path.Combine(root,"private","pair-"+Guid.NewGuid().ToString("N"));
                        var record=Client.PrepareIssued(deployment,root,stage,owner,issued,(phase,harness)=>{Call("/progress",token,new {phase=phase,harness=harness});progress(phase+" "+harness);},cancel);
                        var change=CredentialChange.Prepare(stage,Path.Combine(root,"profiles",kind),Path.Combine(root,"private","backup-"+Guid.NewGuid().ToString("N")));
                        journal.Changes.Add(change);journal.Receipts[kind]=record.SmokeSeconds;Save(journalPath,journal);
                    }
                    cancel.ThrowIfCancellationRequested();Call("/progress",token,new {phase="saving",harness=""});
                    journal.Phase="promoting";Save(journalPath,journal);
                    foreach(var change in journal.Changes) change.Promote();
                    journal.Phase="committing";Save(journalPath,journal);
                    var complete=Call("/complete",token,new {receipts=journal.Receipts});
                    if(Convert.ToString(complete["status"])!="ready") throw new IOException("Portal has not confirmed readiness.");
                    Finish(deployment,root,journal,journalPath);progress("READY");
                } catch {
                    if(journal.Phase=="preparing") {
                        foreach(var change in journal.Changes) change.Rollback();
                        try {Call("/fail",token,new {reason="installation_failed"});} catch { /* Encrypted server journal retries expiry cleanup. */ }
                        File.Delete(journalPath);
                    }
                    throw;
                }
            }
        }
    }
}
