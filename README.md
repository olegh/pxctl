Picaso3d Designer X PRO command line tool
========================

Simple command line tool to monitor 3d-printer state.

Installation
------
```bash
 pip install pxctl
```


Examples
------

#### Discover printer and show it's status continuously

```bash
 pxctl show --continuous
```


#### Specify printer ip address and show its status once

```bash
pxctl show --address=192.168.1.35
```


#### Discover printers and get list in json format

```bash
  pxctl discover --json
 ```


Make printer starts to beep

```bash
  pxctl beep_on --address=192.168.1.35
 ```

Make printer stops to beep

```bash
 pxctl beep_off
 ```

Run hooks when printer success or failure

```bash
 pxctl show --on-success='echo 10' --on-failure='touch /tmp/pxctl_printer_failed'
 ```

Get printer status at json format

```bash 
 pxctl show --json"
 ```

---------------
