using System;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Web.Script.Serialization;

namespace MiniPCConnect {
    public sealed class Artifact {
        public string Version {get;set;}
        public string Url {get;set;}
        public string SHA256 {get;set;}
        public long Size {get;set;}
        public string BinarySHA256 {get;set;}
        public string ZipEntry {get;set;}
    }
    public sealed class Deployment {
        public string SiteId {get;set;}
        public string SiteName {get;set;}
        public string BaseUrl {get;set;}
        public string Model {get;set;}
        public int ContextTokens {get;set;}
        public int OutputTokens {get;set;}
        public string CAFile {get;set;}
        public string CAHash {get;set;}
        public Artifact OpenCode {get;set;}
        public Artifact Claude {get;set;}
        [ScriptIgnore] public string DirectoryPath {get;set;}
        [ScriptIgnore] public string CertificatePath { get { return Path.Combine(DirectoryPath,CAFile); } }
        public static readonly JavaScriptSerializer Json=new JavaScriptSerializer {MaxJsonLength=2*1024*1024};
        public static Uri RequireHttps(string value) {
            Uri uri;
            if(!Uri.TryCreate(value,UriKind.Absolute,out uri) || uri.Scheme!="https" ||
               uri.UserInfo.Length!=0 || uri.Query.Length!=0 || uri.Fragment.Length!=0)
                throw new InvalidDataException("Only an absolute HTTPS URL without credentials/query/fragment is allowed.");
            return uri;
        }
        public static Deployment Load(string path) {
            Deployment d=Json.Deserialize<Deployment>(File.ReadAllText(path,Encoding.UTF8));
            d.DirectoryPath=Path.GetDirectoryName(Path.GetFullPath(path));
            Uri endpoint=RequireHttps(d.BaseUrl);
            if(endpoint.AbsolutePath!="/" || !Regex.IsMatch(d.SiteId ?? "",@"^[a-z0-9][a-z0-9-]{0,48}$") ||
               string.IsNullOrWhiteSpace(d.Model) || d.Model.Length>120 ||
               d.ContextTokens<4096 || d.ContextTokens>1048576 || d.OutputTokens<128 || d.OutputTokens>d.ContextTokens/4)
                throw new InvalidDataException("Invalid deployment identity or context limits.");
            d.BaseUrl=d.BaseUrl.TrimEnd('/');
            if(string.IsNullOrEmpty(d.CAFile) || Path.GetFileName(d.CAFile)!=d.CAFile || !HashValid(d.CAHash))
                throw new InvalidDataException("Invalid public certificate configuration.");
            foreach(Artifact a in new[]{d.OpenCode,d.Claude}) {
                if(a==null || !HashValid(a.SHA256) || !HashValid(a.BinarySHA256) || a.Size<1 || a.Size>1024L*1024*1024)
                    throw new InvalidDataException("Invalid pinned artifact.");
                Uri u=RequireHttps(a.Url);
                if(u.Host!="github.com" && u.Host!="downloads.claude.ai")
                    throw new InvalidDataException("The artifact must use an approved official publisher host.");
                if(!Regex.IsMatch(a.Version ?? "",@"^\d+\.\d+\.\d+$") || (a.ZipEntry!="" && a.ZipEntry!="opencode.exe"))
                    throw new InvalidDataException("Invalid artifact version or archive member.");
            }
            Security.Certificate(d);
            return d;
        }
        static bool HashValid(string s) {return Regex.IsMatch(s ?? "",@"^[0-9a-f]{64}$");}
    }
    public static class Security {
        public static byte[] Protect(byte[] data) {return ProtectedData.Protect(data,null,DataProtectionScope.CurrentUser);}
        public static byte[] Unprotect(byte[] data) {return ProtectedData.Unprotect(data,null,DataProtectionScope.CurrentUser);}
        public static string Hash(byte[] data) {
            using(SHA256 sha=SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(data)).Replace("-","").ToLowerInvariant();
        }
        public static string HashFile(string path) {
            using(SHA256 sha=SHA256.Create()) using(FileStream f=File.OpenRead(path))
                return BitConverter.ToString(sha.ComputeHash(f)).Replace("-","").ToLowerInvariant();
        }
        public static void RequireHash(string path,string expected) {
            if(!string.Equals(HashFile(path),expected,StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("File integrity check failed. Nothing from that download was executed.");
        }
        public static X509Certificate2 Certificate(Deployment d) {
            string pem=File.ReadAllText(d.CertificatePath).Replace("-----BEGIN CERTIFICATE-----","").Replace("-----END CERTIFICATE-----","");
            X509Certificate2 cert=new X509Certificate2(Convert.FromBase64String(pem));
            if(Hash(cert.RawData)!=d.CAHash || DateTime.Now<cert.NotBefore || DateTime.Now>cert.NotAfter)
                throw new InvalidDataException("Pilot certificate fingerprint/validity check failed.");
            bool ca=false;
            foreach(X509Extension ext in cert.Extensions) {
                X509BasicConstraintsExtension basic=ext as X509BasicConstraintsExtension;
                if(basic!=null) ca=basic.CertificateAuthority;
            }
            if(!ca) throw new InvalidDataException("Configured certificate is not a CA.");
            return cert;
        }
        public static bool IsTrusted(Deployment d) {
            using(X509Certificate2 cert=Certificate(d)) {
                foreach(var location in new[]{StoreLocation.CurrentUser,StoreLocation.LocalMachine}) using(var store=new X509Store(StoreName.Root,location)) {
                    store.Open(OpenFlags.ReadOnly);
                    foreach(X509Certificate2 installed in store.Certificates.Find(X509FindType.FindByThumbprint,cert.Thumbprint,false))
                        if(Hash(installed.RawData)==d.CAHash) return true;
                }
            }
            return false;
        }
        public static void TrustForCurrentUser(Deployment d,bool explicitlyApproved) {
            if(!explicitlyApproved) throw new InvalidOperationException("Certificate trust requires explicit user approval.");
            using(X509Certificate2 cert=Certificate(d)) using(X509Store store=new X509Store(StoreName.Root,StoreLocation.CurrentUser)) {
                store.Open(OpenFlags.ReadWrite); store.Add(cert);
            }
        }
        public static void PrivateDirectory(string path) {
            Directory.CreateDirectory(path);
            DirectorySecurity acl=new DirectorySecurity();
            SecurityIdentifier user=WindowsIdentity.GetCurrent().User;
            acl.SetOwner(user); acl.SetAccessRuleProtection(true,false);
            foreach(SecurityIdentifier id in new[]{user,new SecurityIdentifier(WellKnownSidType.LocalSystemSid,null)})
                acl.AddAccessRule(new FileSystemAccessRule(id,FileSystemRights.FullControl,
                    InheritanceFlags.ContainerInherit|InheritanceFlags.ObjectInherit,PropagationFlags.None,AccessControlType.Allow));
            new DirectoryInfo(path).SetAccessControl(acl);
        }
    }
}
