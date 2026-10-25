using System;
using System.IO;
using System.Drawing;
using System.Windows.Forms;
using System.Collections.Generic;
using MiniPCConnect;

public static class UITests {
    static IEnumerable<Control> Children(Control parent) {
        foreach(Control child in parent.Controls) {
            yield return child;
            foreach(Control nested in Children(child)) yield return nested;
        }
    }
    [STAThread]
    public static int Main() {
        Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
        string folder=Path.GetFullPath(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"..","private"));
        Directory.CreateDirectory(folder);
        string unused=Path.Combine(folder,"ui-check-unused-root");
        Deployment d=Deployment.Load(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"pilot.json"));
        using(Wizard window=new Wizard(d,unused)) {
            window.ShowInTaskbar=false; window.Opacity=0; window.Enabled=false;
            window.StartPosition=FormStartPosition.Manual; window.Location=new Point(-32000,-32000);
            window.Show(); Application.DoEvents();
            window.CreateControl();
            int passwordFields=0,programs=0,buttons=0;
            foreach(Control control in Children(window)) {
                control.CreateControl();
                TextBox text=control as TextBox;
                if(text!=null && text.UseSystemPasswordChar) passwordFields++;
                CheckBox check=control as CheckBox;
                if(check!=null && check.Checked) programs++;
                if(control is Button) buttons++;
            }
            window.PerformLayout();
            using(Bitmap bitmap=new Bitmap(window.Width,window.Height)) {
                window.DrawToBitmap(bitmap,new Rectangle(0,0,window.Width,window.Height));
                bitmap.Save(Path.Combine(folder,"installer-layout.png"));
            }
            window.Hide();
            if(passwordFields!=1 || programs!=2 || buttons<5 || window.RightToLeft!=RightToLeft.Yes)
                throw new Exception("Wizard controls missing or wrong defaults");
            if(Directory.Exists(unused)) throw new Exception("Opening wizard unexpectedly installed a profile");
            Console.WriteLine("WinForms controls and offline render passed; no visible window, account or installation created.");
        }
        return 0;
    }
}
