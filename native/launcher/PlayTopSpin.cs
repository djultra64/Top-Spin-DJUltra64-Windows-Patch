// Project-owned portable entry point. Attribution: djultra64.
using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Windows.Forms;

internal static class PlayTopSpin
{
    [STAThread]
    private static int Main()
    {
        try
        {
            string root = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
            string launcher = Path.Combine(root, "TopSpinLauncher.exe");
            if (!File.Exists(launcher))
                throw new FileNotFoundException("TopSpinLauncher.exe is missing. Extract the complete portable package first.");
            // UseShellExecute=false preserves Unicode paths and bypasses file associations.
            // Keep this process alive so Steam tracks the complete launcher/game lifetime.
            var start = new ProcessStartInfo(launcher, "--play") {
                WorkingDirectory = root,
                UseShellExecute = false,
                CreateNoWindow = true
            };
            using (Process child = Process.Start(start))
            {
                if (child == null)
                    throw new InvalidOperationException("The game launcher could not be started.");
                child.WaitForExit();
                return child.ExitCode;
            }
        }
        catch (Exception error)
        {
            MessageBox.Show("Unable to start Top Spin.\n\n" + error.Message,
                "Top Spin", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
