from enum import Enum


class NetPrinterState(Enum):
    npstPrinting = 1
    npstPaused = 2
    npstIdle = 3
    npstService = 4
    npstPrepareForPrinting = 5
    npstPrepareForPause = 6
    npstPrepareForStop = 7
    npstPrePrint = 8


class NetPrinterStatus(Enum):
    npsInitialState = 2147483652
    npsConnectionError = 2147483648
    npsPrintProblem = 1
    npsCriticalError = 2
    npsWaitUser = 3
    npsWaitNewTask = 4
    npsService = 5
    npsMainPrint = 6
    npsPrintDone = 7
    npsPrintPaused = 8
    npsAdjectiveWarning = 9
    npsUpdateDownload = 10


class PrinterType(Enum):
    DesignerXPro = 0
    DesignerPRO250 = 1
    Designer = 2
    DesignerX = 3
    DesignerXL = 4
    DesignerXLPro = 5
    DesignerClassic = 6
    DesignerClassicAdv = 7
    DesignerX2 = 8
    DesignerXL2 = 9
    DesignerXPro2 = 10
    DesignerXLPro2 = 11
    none = -1  # Originally this is "None", had to make it lowercase
