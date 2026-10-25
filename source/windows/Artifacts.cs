using System;
using System.IO;
using System.IO.Compression;
using System.Net.Http;
using System.Threading;

namespace MiniPCConnect {
    public static class Artifacts {
        public static string Ensure(Deployment d,string kind,string root,Action<string> progress,CancellationToken cancel) {
            Artifact a=kind=="opencode"?d.OpenCode:d.Claude;
            string existing=kind=="opencode" ? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),@"npm\node_modules\opencode-ai\bin\opencode.exe")
                : Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),@".local\bin\claude.exe");
            if(File.Exists(existing) && Security.HashFile(existing)==a.BinarySHA256) {
                progress(kind+": استفاده از نسخهٔ نصب‌شده و تأییدشده"); return existing;
            }
            string folder=Path.Combine(root,"binaries",kind+"-"+a.Version);
            Security.PrivateDirectory(folder);
            string binary=Path.Combine(folder,kind=="opencode"?"opencode.exe":"claude.exe");
            if(File.Exists(binary)) {Security.RequireHash(binary,a.BinarySHA256); return binary;}
            string temporary=Path.Combine(folder,"download-"+Guid.NewGuid().ToString("N")+".part");
            try {
                using(CancellationTokenSource deadline=CancellationTokenSource.CreateLinkedTokenSource(cancel))
                using(HttpClient http=new HttpClient(new HttpClientHandler {AllowAutoRedirect=false}) {Timeout=TimeSpan.FromMinutes(8)}) {
                    deadline.CancelAfter(TimeSpan.FromMinutes(8));
                    Uri url=Deployment.RequireHttps(a.Url);
                    HttpResponseMessage response=null;
                    for(int redirects=0;redirects<6;redirects++) {
                        response=http.GetAsync(url,HttpCompletionOption.ResponseHeadersRead,deadline.Token).GetAwaiter().GetResult();
                        int status=(int)response.StatusCode;
                        if(status<300 || status>=400) break;
                        Uri location=response.Headers.Location;
                        if(location==null) throw new IOException("Download redirect has no destination.");
                        url=Deployment.RequireHttps(new Uri(url,location).AbsoluteUri); response.Dispose(); response=null;
                    }
                    if(response==null) throw new IOException("Too many download redirects.");
                    using(response) {
                        response.EnsureSuccessStatusCode();
                        using(Stream source=response.Content.ReadAsStreamAsync().GetAwaiter().GetResult())
                        using(FileStream dest=new FileStream(temporary,FileMode.CreateNew,FileAccess.Write)) {
                            byte[] buffer=new byte[128*1024]; long total=0,lastNotice=-1;
                            while(true) {
                                int read=source.ReadAsync(buffer,0,buffer.Length,deadline.Token).GetAwaiter().GetResult();
                                if(read==0) break;
                                total+=read; if(total>a.Size) throw new IOException("Download exceeds its pinned size.");
                                dest.Write(buffer,0,read);
                                long percent=total*100/a.Size;
                                if(percent!=lastNotice) {progress(kind+": دریافت از منبع رسمی — "+percent+"٪");lastNotice=percent;}
                            }
                            if(total!=a.Size) throw new IOException("Download is incomplete.");
                        }
                    }
                }
                Security.RequireHash(temporary,a.SHA256); cancel.ThrowIfCancellationRequested();
                if(a.ZipEntry!="") {
                    using(ZipArchive archive=ZipFile.OpenRead(temporary)) {
                        ZipArchiveEntry entry=archive.GetEntry(a.ZipEntry);
                        if(entry==null || entry.Length<1 || entry.Length>1024L*1024*1024) throw new IOException("Expected native binary is absent from archive.");
                        // Extract only the explicit single binary; never extract arbitrary archive paths.
                        using(Stream source=entry.Open()) using(FileStream dest=new FileStream(binary,FileMode.CreateNew)) source.CopyTo(dest);
                    }
                } else File.Move(temporary,binary);
                Security.RequireHash(binary,a.BinarySHA256);
                progress(kind+": نسخه و صحت فایل تأیید شد"); return binary;
            } catch {
                if(File.Exists(binary)) File.Delete(binary); // Only this newly-created owned artifact.
                throw;
            } finally {if(File.Exists(temporary)) File.Delete(temporary);}
        }
    }
}
