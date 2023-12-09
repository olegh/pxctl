Picaso Designer X PRO command line tool
========================

Simple command line tool to monitor 3d-printer state.

### Installation
```
pip install pxctl
```

### Examples

Discover printer and show it's status continuously
```
 pxctl show --continuous
```

Specify printer ip address and show its status once
```
pxctl show --address=192.168.1.35
```

Discover printers and get list in json format

```
pxctl discover --json
```

Make printer starts to beep
```
pxctl beep_on --address=192.168.1.35
```

Make printer stops to beep
```
pxctl beep_off
```

Run hooks when printer success or failure
```
pxctl show --on-success='echo 10' --on-failure='touch /tmp/pxctl_printer_failed'
```

Get printer status at json format
```
pxctl show --json"
```

---------------
