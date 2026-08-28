# linebot

Environment note

This project assumes you are using a Windows laptop (example: Lenovo) running an Ubuntu distribution via WSL2. All ROS / robotics components must be executed inside the Ubuntu WSL environment — do not run ROS nodes or build the workspace from native Windows.

If your robot connects over USB (Arduino, serial devices), use the `usbipd-win` flow to share and attach the device into WSL. Example PowerShell commands:

```powershell
usbipd list
usbipd bind --busid <busid>            # requires Administrator
usbipd attach --wsl --busid <busid>    # attach to WSL
usbipd detach --busid <busid>          # detach when finished
```

See Microsoft's guidance: https://learn.microsoft.com/windows/wsl/connect-usb for details and troubleshooting.

I was here!