# Shows one Windows toast notification. Called by notify.py.
# Text comes from the environment variables NOTIFY_TITLE and NOTIFY_BODY
# (not from arguments: a value that starts with "-" or holds non-ASCII text
# would be mangled). InnerText escapes "<" and "&" in the toast XML.
# Comments are ASCII only: Windows PowerShell 5.1 reads a .ps1 without a BOM
# as the ANSI code page.
try {
    [void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
    [void][Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]
    $template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02
    $xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template)
    $texts = $xml.GetElementsByTagName('text')
    $texts.Item(0).InnerText = [string]$env:NOTIFY_TITLE
    $texts.Item(1).InnerText = [string]$env:NOTIFY_BODY
    $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
    # The notifier id of Windows PowerShell, so no extra registration is needed.
    $appId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
} catch {
    # A notification failure must never disturb Claude Code.
}
exit 0
