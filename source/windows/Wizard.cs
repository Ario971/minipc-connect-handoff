using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using System.Drawing;
using System.Windows.Forms;
using System.Threading;
using System.Threading.Tasks;
using System.Reflection;

namespace MiniPCConnect {
    public static class Program {
        static string Option(string[] args,string name,string fallback) {
            int i=Array.IndexOf(args,name); return i>=0 && i+1<args.Length?args[i+1]:fallback;
        }
        public static List<ProfileRecord> Setup(Deployment d,string root,string username,string password,string[] kinds,Action<string> progress,CancellationToken cancel) {
            if(!Environment.Is64BitOperatingSystem || !Environment.Is64BitProcess) throw new InvalidOperationException("This pilot package requires Windows x64.");
            if(!Security.IsTrusted(d)) throw new InvalidOperationException("Approve the verified pilot certificate for the current Windows user first.");
            foreach(string kind in kinds) if(kind!="opencode" && kind!="claude") throw new ArgumentException("Unknown harness");
            var records=new List<ProfileRecord>();
            using(Gateway gateway=new Gateway(d)) {
                progress("ورود امن با حساب موجود LiteLLM"); gateway.Login(username,password); password=null;
                Security.PrivateDirectory(root);
                if((File.GetAttributes(root)&FileAttributes.ReparsePoint)!=0) throw new IOException("Installation root cannot be a link or junction.");
                foreach(string kind in kinds) {
                    cancel.ThrowIfCancellationRequested(); records.Add(Client.Install(d,gateway,kind,root,progress,cancel));
                }
            }
            string exe=Path.Combine(root,"MiniPCConnect.exe");
            string source=Assembly.GetExecutingAssembly().Location;
            if(!string.Equals(source,exe,StringComparison.OrdinalIgnoreCase)) File.Copy(source,exe,true);
            foreach(string name in new[]{"pilot.json",d.CAFile}) {
                string from=Path.Combine(d.DirectoryPath,name),to=Path.Combine(root,name);
                if(!string.Equals(from,to,StringComparison.OrdinalIgnoreCase)) File.Copy(from,to,true);
            }
            Directory.CreateDirectory(Path.Combine(root,"workspace"));
            foreach(ProfileRecord record in records) {
                string command="@echo off\r\n\""+exe+"\" --launch "+record.Harness+"\r\n";
                File.WriteAllText(Path.Combine(root,"Start-"+record.Harness+".cmd"),command,Encoding.Default);
            }
            File.WriteAllText(Path.Combine(root,"acceptance.json"),Deployment.Json.Serialize(new {timestamp=DateTime.UtcNow.ToString("o"),profiles=records}),Encoding.UTF8);
            return records;
        }
        [STAThread] public static int Main(string[] args) {
            try {
                string config=Option(args,"--config",Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"pilot.json"));
                Deployment d=Deployment.Load(config);
                string root=Path.GetFullPath(Option(args,"--root",Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"MiniPCConnect",d.SiteId+"-portal-v2")));
                if(Array.IndexOf(args,"--acceptance")>=0) {
                    var input=Deployment.Json.Deserialize<Dictionary<string,object>>(Console.In.ReadToEnd());
                    var result=Setup(d,root,Convert.ToString(input["username"]),Convert.ToString(input["password"]),new[]{"opencode","claude"},s=>Console.WriteLine(s),CancellationToken.None);
                    Console.WriteLine(Deployment.Json.Serialize(new {passed=true,profiles=result})); return 0;
                }
                Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
                string launch=Option(args,"--launch",null);
                if(launch!=null) {
                    using(FolderBrowserDialog picker=new FolderBrowserDialog {Description="پوشهٔ پروژه را انتخاب کن",SelectedPath=Path.Combine(root,"workspace")}) {
                        if(picker.ShowDialog()==DialogResult.OK) Client.Launch(d,launch,root,picker.SelectedPath);
                    }
                } else if(Array.IndexOf(args,"--classic")>=0) Application.Run(new Wizard(d,root));
                else {
                    bool acceptance=Array.IndexOf(args,"--pair-acceptance")>=0;
                    using(var portal=new Portal(d)) portal.Run(root,!acceptance,s=>{if(acceptance)Console.WriteLine(s);},CancellationToken.None);
                    if(!acceptance) MessageBox.Show("اتصال آماده است. از منوی Start، پوشه MiniPC Connect را باز و برنامه را اجرا کن.\n"+root,"MiniPC Connect",MessageBoxButtons.OK,MessageBoxIcon.Information);
                }
                return 0;
            } catch(Exception error) {
                if(Array.IndexOf(args,"--acceptance")>=0 || Array.IndexOf(args,"--pair-acceptance")>=0) Console.Error.WriteLine(error.ToString());
                else MessageBox.Show(error.Message,"MiniPC Connect — نیاز به بررسی",MessageBoxButtons.OK,MessageBoxIcon.Warning);
                return 1;
            }
        }
    }
    public sealed class Wizard : Form {
        readonly Deployment deployment; readonly string root;
        readonly TextBox email=new TextBox(),password=new TextBox(),log=new TextBox(),project=new TextBox();
        readonly CheckBox opencode=new CheckBox(),claude=new CheckBox();
        readonly Button install=new Button(),trust=new Button(),cancel=new Button(),openOC=new Button(),openCC=new Button();
        readonly Label state=new Label(); readonly ProgressBar progress=new ProgressBar();
        CancellationTokenSource cancellation; bool busy;
        public Wizard(Deployment d,string path) {
            deployment=d; root=path;
            Text="MiniPC Connect — راه‌اندازی اتصال"; Size=new Size(920,810); MinimumSize=new Size(800,720);
            StartPosition=FormStartPosition.CenterScreen; BackColor=Color.FromArgb(248,250,252);
            Font=new Font("Segoe UI",10.5F); RightToLeft=RightToLeft.Yes; RightToLeftLayout=true; AutoScaleMode=AutoScaleMode.Dpi;
            var content=new TableLayoutPanel {Dock=DockStyle.Fill,Padding=new Padding(26),ColumnCount=1,RowCount=13,AutoScroll=true};
            content.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100)); Controls.Add(content);
            var heading=new Label {Text="MiniPC Connect",Font=new Font("Segoe UI",24,FontStyle.Bold),ForeColor=Color.FromArgb(30,58,95),AutoSize=true,RightToLeft=RightToLeft.No};
            content.Controls.Add(heading);
            content.Controls.Add(new Label {Text="مدل روی MiniPC می‌ماند؛ ابزارهای کار روی همین لپ‌تاپ اجرا می‌شوند.",AutoSize=true,Margin=new Padding(0,4,0,14)});
            var host=new Label {Text=d.BaseUrl+"  •  "+d.Model,AutoSize=true,RightToLeft=RightToLeft.No,ForeColor=Color.FromArgb(71,85,105)}; content.Controls.Add(host);
            trust.Text=Security.IsTrusted(d)?"HTTPS برای حساب ویندوز شما معتبر است":"۱. بررسی و تأیید گواهی اتصال";
            trust.AutoSize=true; trust.MinimumSize=new Size(300,38); trust.Enabled=!Security.IsTrusted(d); trust.Click+=ApproveCertificate;
            content.Controls.Add(trust);
            var login=new TableLayoutPanel {AutoSize=true,Dock=DockStyle.Top,ColumnCount=2,Margin=new Padding(0,14,0,10)};
            login.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,130)); login.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100));
            login.Controls.Add(new Label {Text="ایمیل حساب",AutoSize=true},0,0); email.Dock=DockStyle.Fill; email.RightToLeft=RightToLeft.No; email.AccessibleName="ایمیل حساب LiteLLM"; login.Controls.Add(email,1,0);
            login.Controls.Add(new Label {Text="رمز حساب",AutoSize=true},0,1); password.Dock=DockStyle.Fill; password.UseSystemPasswordChar=true; password.RightToLeft=RightToLeft.No; password.AccessibleName="رمز حساب LiteLLM"; login.Controls.Add(password,1,1);
            content.Controls.Add(login);
            content.Controls.Add(new Label {Text="اگر حساب نداری، مدیر باید از پنل LiteLLM برایت دعوت‌نامه بسازد. رمز اینجا ذخیره نمی‌شود.",AutoSize=true,MaximumSize=new Size(810,0)});
            var choices=new FlowLayoutPanel {AutoSize=true,Dock=DockStyle.Top,Margin=new Padding(0,12,0,6)};
            opencode.Text="OpenCode"; claude.Text="Claude Code — حالت سبک و آزمایشی"; opencode.Checked=true;claude.Checked=true;opencode.AutoSize=true;claude.AutoSize=true;
            choices.Controls.Add(opencode); choices.Controls.Add(claude); content.Controls.Add(choices);
            content.Controls.Add(new Label {Text="۲. نصب نسخهٔ تأییدشده، ساخت کلید جدا و آزمون واقعی. برنامه‌ها و تنظیمات قبلی تغییر نمی‌کنند.",AutoSize=true,MaximumSize=new Size(810,0)});
            var actions=new FlowLayoutPanel {AutoSize=true,Dock=DockStyle.Top,Margin=new Padding(0,10,0,8)};
            install.Text="نصب و اتصال خودکار"; install.BackColor=Color.FromArgb(37,99,235);install.ForeColor=Color.White;install.FlatStyle=FlatStyle.Flat;install.Size=new Size(235,43); install.Click+=Install;
            cancel.Text="توقف";cancel.Size=new Size(100,43);cancel.Enabled=false;cancel.Click+=(s,e)=>{if(cancellation!=null)cancellation.Cancel();};
            actions.Controls.Add(install);actions.Controls.Add(cancel);content.Controls.Add(actions);
            progress.Dock=DockStyle.Top;progress.Height=8;content.Controls.Add(progress);
            state.AutoSize=true;state.Text="آمادهٔ شروع — درخواست مدل پولی یا ابری ارسال نمی‌شود.";state.Margin=new Padding(0,8,0,5);content.Controls.Add(state);
            log.Multiline=true;log.ReadOnly=true;log.Height=105;log.Dock=DockStyle.Top;log.ScrollBars=ScrollBars.Vertical;log.BackColor=Color.White;log.AccessibleName="وضعیت مراحل نصب";content.Controls.Add(log);
            var launchArea=new FlowLayoutPanel {AutoSize=true,Dock=DockStyle.Top,Margin=new Padding(0,12,0,0)};
            var choose=new Button {Text="انتخاب پوشهٔ پروژه",AutoSize=true,Height=38};choose.Click+=(s,e)=>{using(var picker=new FolderBrowserDialog())if(picker.ShowDialog()==DialogResult.OK)project.Text=picker.SelectedPath;};
            project.Text=Path.Combine(root,"workspace");project.Width=340;project.RightToLeft=RightToLeft.No;
            openOC.Text="اجرای OpenCode";openCC.Text="اجرای Claude Code";openOC.AutoSize=true;openCC.AutoSize=true;
            openOC.Enabled=File.Exists(Path.Combine(root,"profiles","opencode","profile.json"));openCC.Enabled=File.Exists(Path.Combine(root,"profiles","claude","profile.json"));
            openOC.Click+=(s,e)=>Launch("opencode");openCC.Click+=(s,e)=>Launch("claude");
            launchArea.Controls.Add(choose);launchArea.Controls.Add(project);launchArea.Controls.Add(openOC);launchArea.Controls.Add(openCC);content.Controls.Add(launchArea);
            FormClosing+=(s,e)=>{if(busy){e.Cancel=true;MessageBox.Show("ابتدا توقف را بزن و منتظر پایان مرحلهٔ جاری بمان.","نصب در حال اجراست");}};
        }
        void ApproveCertificate(object sender,EventArgs e) {
            string message="این کار گواهی ریشهٔ همین پایلوت را فقط برای حساب ویندوز شما معتبر می‌کند. گواهی‌های صادرشده توسط آن نیز مورد اعتماد خواهند بود. بررسی HTTPS خاموش نمی‌شود.\n\nSHA256:\n"+deployment.CAHash+"\n\nفقط اگر بسته را از مدیر مورد اعتماد گرفته‌ای، تأیید کن.";
            if(MessageBox.Show(message,"تأیید اعتماد به گواهی",MessageBoxButtons.YesNo,MessageBoxIcon.Warning,MessageBoxDefaultButton.Button2)!=DialogResult.Yes)return;
            try {Security.TrustForCurrentUser(deployment,true);trust.Enabled=false;trust.Text="HTTPS برای حساب ویندوز شما معتبر است";} catch(Exception error){MessageBox.Show(error.Message);}
        }
        async void Install(object sender,EventArgs e) {
            var selected=new List<string>();if(opencode.Checked)selected.Add("opencode");if(claude.Checked)selected.Add("claude");
            if(selected.Count==0 || string.IsNullOrWhiteSpace(email.Text) || password.Text.Length==0) {MessageBox.Show("ایمیل، رمز و حداقل یک برنامه را مشخص کن.");return;}
            string username=email.Text.Trim(),secret=password.Text;password.Clear();
            busy=true;install.Enabled=false;email.Enabled=false;password.Enabled=false;cancel.Enabled=true;progress.Style=ProgressBarStyle.Marquee;
            cancellation=new CancellationTokenSource();
            Action<string> report=text=>BeginInvoke(new Action(()=>{state.Text=text;log.AppendText(text+Environment.NewLine);}));
            try {
                var records=await Task.Run(()=>Program.Setup(deployment,root,username,secret,selected.ToArray(),report,cancellation.Token));
                foreach(ProfileRecord item in records) {if(item.Harness=="opencode")openOC.Enabled=true;else openCC.Enabled=true;}
                state.Text="آماده — آزمون واقعی موفق بود. پوشهٔ پروژه را انتخاب کن و برنامه را اجرا کن.";state.ForeColor=Color.FromArgb(21,128,61);
            } catch(Exception error) {state.Text="نصب کامل نشد؛ وضعیت آماده اعلام نمی‌شود.";state.ForeColor=Color.FromArgb(185,28,28);log.AppendText(error.Message+Environment.NewLine);}
            finally {secret=null;busy=false;install.Enabled=true;email.Enabled=true;password.Enabled=true;cancel.Enabled=false;progress.Style=ProgressBarStyle.Blocks;cancellation.Dispose();cancellation=null;}
        }
        void Launch(string kind) {try {Client.Launch(deployment,kind,root,project.Text);}catch(Exception error){MessageBox.Show(error.Message,"اتصال نیاز به بررسی دارد");}}
    }
}
