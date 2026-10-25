using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using System.Diagnostics;
using MiniPCConnect;

public static class Tests {
    static int count;
    static void Check(bool yes, string message) { if (!yes) throw new Exception(message); count++; }
    static void Refuse(Action action, string message) {
        bool refused=false; try { action(); } catch { refused=true; } Check(refused,message);
    }
    public static int Main() {
        string root=Path.Combine(Path.GetTempPath(),"minipc-connect-tests-"+Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try {
            Deployment d=Deployment.Load(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"pilot.json"));
            Check(d.Model=="local-coder", "deployment model");
            Refuse(()=>Deployment.RequireHttps("http://192.168.178.65"),"plaintext transport refused");
            Refuse(()=>Deployment.RequireHttps("https://name:password@example.com/"),"URL credentials refused");
            Check(Deployment.RequireHttps("https://192.168.178.65:9443").Scheme=="https","HTTPS accepted");
            byte[] input=Encoding.UTF8.GetBytes("synthetic-not-a-real-key");
            byte[] protectedValue=Security.Protect(input);
            Check(Encoding.UTF8.GetString(protectedValue).IndexOf("synthetic-not-a-real-key",StringComparison.Ordinal)<0,"ciphertext only");
            Check(Encoding.UTF8.GetString(Security.Unprotect(protectedValue))=="synthetic-not-a-real-key","DPAPI roundtrip");
            Refuse(()=>Security.Unprotect(new byte[]{1,2,3}),"bad DPAPI rejected");
            string file=Path.Combine(root,"fixture.txt"); File.WriteAllText(file,"test");
            Refuse(()=>Security.RequireHash(file,new string('0',64)),"wrong artifact hash rejected");
            Security.RequireHash(file,Security.HashFile(file)); count++;
            string oc=Path.Combine(root,"opencode"), cc=Path.Combine(root,"claude");
            ProcessStartInfo o=Client.StartInfo(d,"opencode",oc,"oc-secret",root,false);
            ProcessStartInfo c=Client.StartInfo(d,"claude",cc,"cc-secret",root,false);
            Check(o.EnvironmentVariables["HOME"]!=c.EnvironmentVariables["HOME"],"separate homes");
            Check(o.EnvironmentVariables["XDG_DATA_HOME"]!=c.EnvironmentVariables["XDG_DATA_HOME"],"separate history");
            Check(c.EnvironmentVariables["ANTHROPIC_API_KEY"]=="cc-secret","only client key");
            Check(o.EnvironmentVariables["ANTHROPIC_API_KEY"]==null,"no inherited Claude credential");
            Check(c.EnvironmentVariables["MINIPC_PILOT_API_KEY"]==null,"no inherited OpenCode credential");
            Check(c.EnvironmentVariables["NODE_TLS_REJECT_UNAUTHORIZED"]==null,"no TLS bypass");
            Check(c.Arguments.Contains("--bare") && c.Arguments.Contains("manual"),"native lightweight manual mode");
            Check(!c.Arguments.Contains("skip-permissions") && !c.Arguments.Contains("fallback"),"no unsafe fallback");
            Check(c.EnvironmentVariables["CLAUDE_CODE_MAX_CONTEXT_TOKENS"]=="16384","context cap");
            Check(Client.Quote("C:\\")=="\"C:\\\\\"","quoted root path preserves trailing separator");
            var body=Gateway.KeyRequest("test-user","test-alias",d.Model);
            Check((string)body["key_type"]=="llm_api" && !body.ContainsKey("allowed_routes"),"normal users request the standard API-only preset");
            Check((int)body["max_parallel_requests"]==1 && (string)body["duration"]=="30d","limited expiring keys");
            Check((string)body["key_type"]=="llm_api","inference only");
            Security.PrivateDirectory(Path.Combine(root,"private")); count++;
            Refuse(()=>Client.RequireEmptyProfile(root),"existing profile not overwritten");
            Check(Portal.PairUrl(d,"ABCD234567")==d.BaseUrl+"/connect/#pair=ABCD234567","public code only in pair URL");
            Refuse(()=>Portal.PairUrl(d,"../bad?secret=x"),"bad pair code rejected");
            string profile=Path.Combine(root,"rotation");Security.PrivateDirectory(profile);
            var previous=new ProfileRecord {UserId="alice",Gateway=d.BaseUrl,Model=d.Model,Ready=true,Harness="opencode"};
            File.WriteAllText(Path.Combine(profile,"profile.json"),Deployment.Json.Serialize(previous));
            File.WriteAllBytes(Path.Combine(profile,"key.dpapi"),protectedValue);
            Refuse(()=>Client.RequireOwner(d,profile,"bob"),"different owner cannot replace credentials");
            Client.RequireOwner(d,profile,"alice");Check(true,"same owner may renew");
            string stage=Path.Combine(root,"rotation-stage");Security.PrivateDirectory(stage);
            File.WriteAllText(Path.Combine(stage,"profile.json"),Deployment.Json.Serialize(previous));
            File.WriteAllBytes(Path.Combine(stage,"key.dpapi"),Security.Protect(Encoding.UTF8.GetBytes("new-synthetic")));
            var change=CredentialChange.Prepare(stage,profile,Path.Combine(root,"rotation-backup"));
            change.Promote();Check(Client.ReadKey(profile)=="new-synthetic","new credential promoted");
            change.Rollback();Check(Client.ReadKey(profile)=="synthetic-not-a-real-key","failed setup restores old credential");
            change.MarkReady();Check(Deployment.Json.Deserialize<ProfileRecord>(File.ReadAllText(Path.Combine(profile,"profile.json"))).Ready,"ready metadata atomically saved");
            string checkpoint=Path.Combine(root,"checkpoint.json");
            for(int i=0;i<25;i++) AtomicFile.Write(checkpoint,i.ToString());
            Check(File.ReadAllText(checkpoint)=="24","bounded atomic checkpoint replacement");
            Console.WriteLine(count+" native contracts passed"); return 0;
        } catch(Exception e) { Console.Error.WriteLine(e.ToString()); return 1; }
        finally { if(Path.GetFileName(root).StartsWith("minipc-connect-tests-")) Directory.Delete(root,true); }
    }
}
