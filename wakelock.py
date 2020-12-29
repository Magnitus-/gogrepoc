import ctypes
import platform
import sys
import xml.etree.ElementTree

if not ((platform.system() == "Darwin") or (platform.system() == "Windows")):
    try:
        import PyQt5.QtDBus
    except ImportError:
        pass

if (platform.system() == "Darwin"):
    import CoreFoundation
    import objc

class Wakelock: 
    #Mac Sleep support based on caffeine : https://github.com/jpn--/caffeine by Jeffrey Newman

    def __init__(self):
       
        if (platform.system() == "Windows"):
            self.ES_CONTINUOUS        = 0x80000000
            self.ES_AWAYMODE_REQUIRED = 0x00000040
            self.ES_SYSTEM_REQUIRED   = 0x00000001
            self.ES_DISPLAY_REQUIRED  = 0x00000002
            #Windows is not particularly consistent on what is required for a wakelock for a script that often uses a USB device, so define WAKELOCK for easy changing. This works on Windows 10 as of the October 2017 update.  
            self.ES_WAKELOCK = self.ES_CONTINUOUS | self.ES_SYSTEM_REQUIRED
            
        if (platform.system() == "Darwin"):
            
            self.PM_NODISPLAYSLEEP = 'NoDisplaySleepAssertion'
            self.PM_NOIDLESLEEP = "NoIdleSleepAssertion"
            self.PM_WAKELOCK = self.PM_NOIDLESLEEP
            self._kIOPMAssertionLevelOn = 255
            
            self.libIOKit = ctypes.cdll.LoadLibrary('/System/Library/Frameworks/IOKit.framework/IOKit')
            self.libIOKit.IOPMAssertionCreateWithName.argtypes = [ ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32) ]
            self.libIOKit.IOPMAssertionRelease.argtypes = [ ctypes.c_uint32 ]
            self._PMassertion = None 
            self._PMassertID = ctypes.c_uint32(0) 
            self._PMerrcode = None
            self._IOPMAssertionRelease = self.libIOKit.IOPMAssertionRelease
                
                
    def _CFSTR(self, py_string):
        return CoreFoundation.CFStringCreateWithCString(None, py_string, CoreFoundation.kCFStringEncodingASCII)

    def raw_ptr(self, pyobjc_string):
        return objc.pyobjc_id(pyobjc_string.nsstring())

    def _IOPMAssertionCreateWithName(self, assert_name, assert_level, assert_msg):
        assertID = ctypes.c_uint32(0)
        p_assert_name = self.raw_ptr(self._CFSTR(assert_name))
        p_assert_msg = self.raw_ptr(self._CFSTR(assert_msg))
        errcode = self.libIOKit.IOPMAssertionCreateWithName(p_assert_name,
            assert_level, p_assert_msg, ctypes.byref(assertID))
        return (errcode, assertID)
                    

    def _get_inhibitor(self):
        #try:
        #    return GnomeSessionInhibitor()
        #except Exception as e:
        #    debug("Could not initialise the gnomesession inhibitor: %s" % e)

        #try:
        #    return DBusSessionInhibitor('org.gnome.PowerManager',"/org/gnome/PowerManager",'org.gnome.PowerManager')
        #except Exception as e:
        #    debug("Could not initialise the gnome power manager inhibitor: %s" % e)
            

        #try:
        #    return DBusSessionInhibitor('.org.freedesktop.PowerManagement','/org/freedesktop/PowerManagement/Inhibit','org.freedesktop.PowerManagement.Inhibit')
        #except Exception as e:
        #    debug("Could not initialise the freedesktop power management inhibitor: %s" % e)

            
        try:
            return DBusSystemInhibitor('org.freedesktop.login1','/org/freedesktop/login1','org.freedesktop.login1.Manager')
        except Exception as e:
            warn("Could not initialise the systemd session inhibitor: %s" % e)
            

        return None

    
    def take_wakelock(self):    
        if platform.system() == "Windows":
            ctypes.windll.kernel32.SetThreadExecutionState(self.ES_WAKELOCK)
        if platform.system() == "Darwin":
            a = self.PM_WAKELOCK
            if self._PMassertion is not None and a != self._PMassertion:
                self.release_wakelock()
            if self._PMassertID.value ==0:
                self._PMerrcode, self._PMassertID = self._IOPMAssertionCreateWithName(a,self._kIOPMAssertionLevelOn,"gogrepoc")
                self._PMassertion = a
        if (not (platform.system() == "Windows" or platform.system() == "Darwin")) and  ('PyQt5.QtDBus' in sys.modules):
            self.inhibitor = self._get_inhibitor()
            self.inhibitor.inhibit()
        
    def release_wakelock(self):
        if platform.system() == "Windows":
            ctypes.windll.kernel32.SetThreadExecutionState(self.ES_CONTINUOUS)
        if platform.system() == "Darwin":
            self._PMerrcode = self._IOPMAssertionRelease(self._PMassertID)
            self._PMassertID.value = 0
            self._PMassertion = None
            
class DBusSystemInhibitor:
    
    def __init__(self, name, path, interface, method=["Inhibit"]):
        self.name = name
        self.path = path
        self.interface_name = interface
        self.method = method
        self.cookie = None
        self.APPNAME = "GOGRepo Gamma"
        self.REASON = "Using Internet and USB Connection"
        bus = PyQt5.QtDBus.QDBusConnection.systemBus()
        introspection = PyQt5.QtDBus.QDBusInterface(self.name,self.path,"org.freedesktop.DBus.Introspectable",bus) 
        serviceIntrospection = xml.etree.ElementTree.fromstring(PyQt5.QtDBus.QDBusReply(introspection.call("Introspect")).value())
        methodExists = False;                                             
        for interface in serviceIntrospection.iter("interface"):
            if interface.get('name') == self.interface_name:      
                for method in interface.iter("method"):
                    if method.get('name') == self.method[0]:
                        methodExists = True
        if not methodExists:
            raise AttributeError(self.interface_name + "has no method " + self.method[0])
        self.iface = PyQt5.QtDBus.QDBusInterface(self.name,self.path,self.interface_name,bus)   
        
    def inhibit(self):
        if self.cookie is None:
            reply = PyQt5.QtDBus.QDBusReply(self.iface.call(self.method[0],"idle",self.APPNAME, self.REASON,"block"))
            if reply.isValid():
                self.cookie = reply.value()
        
    def uninhibit(self):
        if (self.cookie is not None):
            pass #It's not possible to release this file handle in QtDBus (since the QDUnixFileDescriptor is a copy). The file handle is automatically released when the program exits. 
                


            
class DBusSessionInhibitor:
    def __init__(self,name, path, interface, methods=["Inhibit", "UnInhibit"] ):
        self.name = name
        self.path = path
        self.interface_name = interface
        self.methods = methods
        self.cookie = None
        self.APPNAME = "GOGRepo Gamma"
        self.REASON = "Using Internet and USB Connection"

        bus = PyQt5.QtDBus.QDBusConnection.sessionBus()
        self.iface = PyQt5.QtDBus.QDBusInterface(self.name,self.path,self.interface_name,bus)   


    def inhibit(self):
        if self.cookie is None:
            self.cookie = PyQt5.QtDbus.QDBusReply(self.iface.call(self.methods[0],self.APPNAME, self.REASON)).value()

    def uninhibit(self):
        if self.cookie is not None:
            self.iface.call(self.methods[1],self.cookie)
            self.cookie = None

class GnomeSessionInhibitor(DBusSessionInhibitor):
    TOPLEVEL_XID = 0
    INHIBIT_SUSPEND = 4

    def __init__(self):
        DBusSessionInhibitor.__init__(self, 'org.gnome.SessionManager',
                                '/org/gnome/SessionManager',
                                "org.gnome.SessionManager",
                                ["Inhibit", "Uninhibit"])

    def inhibit(self):
        if self.cookie is None:
            self.cookie = PyQt5.QtDbus.QDBusReply(self.iface.call(self.methods[0],self.APPNAME,GnomeSessionInhibitor.TOPLEVEL_XID, self.REASON),GnomeSessionInhibitor.INHIBIT_SUSPEND).value()