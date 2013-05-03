#!/usr/bin/python

from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from os import system
import libvirt
from urlparse import urlparse
import cgi
import json
import sys

#SAMPLE GET RQSTS
#vm_creation-> http://server/vm/create?name=test_vm&vm_type=vtype&image_type=itype
#note: instance_type changed to vm_type
#note: _x86_ or _x86_64_

PORT = 8088
request_ = "http://192.168.56.101:8088/vm/create?name=test_vm&vm_type=1&image_type=0"
LOC_IMG = "/var/lib/libvirt/images/" #append the flavor name at the to create whole path
runningVM = {} #dict of all currnt VMs
vmID = 1 #uniq to all machines ever ran. shud begin with +ve
domDic = {}
MACHINE = 'root@192.168.56.101' #ip of machine to connect to
allmachines = []
runningMachs = {} #stores the no. of remaning processrs for all running machines
procDic = {}
mach_id_nam = {}

pm_file = None
vm_type = None
image_file = None

vm_type = "data/Vm_types.php"
image_file = "data/myimgs.php"
pm_file = "data/mymachines.php"

def getVMdesc (vmtype):
  vmString = open (vm_type, 'r').read()
  dic = json.loads(vmString)
  for i in dic['types']:
    if i['tid'] == vmtype:
      return i

def getFlavor (path):
  localAddr = path[path.find(':')+1 : ]
  return localAddr.split('/')[-1]

def check (vm, vmName):
  for vms in runningVM:
    tmp = runningVM[int(vms)]
    if tmp['name'] == vmName:
      print "VM: " + tmp['name'] + " already exists!"
      return 0
  return 1

def selectMachine_(vm, imgpath):
  global runningMachs
  global mach_id_nam
  memreq = int(vm['ram'])
  numprocreq = int(vm['cpu'])
  mindiffmem = 10000000
  changed = False

  typ = 0
  if imgpath.find('64') >= 0:
    typ = 1

  allmachines = open (pm_file, 'r').read().split("\n")
  selectMach = allmachines[0]

  for machine in allmachines:
    if len(machine) == 0 or machine.find('\n')>=0:
      continue
    conn = libvirt.open ('remote+ssh://'+machine+'/system')
    params = conn.getInfo()
    if machine not in runningMachs:
      capmem = params[1] #->[8]
      capcpu = params[2] #->[9]
      params.append(capmem)
      params.append(capcpu)
      runningMachs[machine] = params

    if (runningMachs[machine][0].find('64') >= 0 and typ == 1) or (runningMachs[machine][0].find('64') < 0 and typ == 0):
      diffmem = runningMachs[machine][1] - memreq
      diffproc = runningMachs[machine][2] - numprocreq
      if diffmem <= mindiffmem and diffproc >= 0 and diffmem >= 0:
        selectMach = machine
  mindiffmem = diffmem
	changed = True

  i=0
  pmid = -1
  while 1:
    if selectMach == allmachines[i]:
      pmid = i+1
      break
    i += 1

  if pmid > 0:
    mach_id_nam[pmid] = selectMach

  if changed == False or pmid == -1:
    return (-1, -1)

  runningMachs[selectMach][1] -= memreq
  runningMachs[selectMach][2] -= numprocreq
  return (selectMach, pmid)

 
def create (vm, imgpath, vmName):
  global vmID
  global domDic
  #currently only qemu considered
  
  if check (vm, vmName) == 0:
    print "machine Name already exists"
    return 0

  flavor = getFlavor(imgpath)
  
  (MACHINE, pmid) = selectMachine_(vm, imgpath)
  if pmid == -1:
    print "No suitable machine present"
    return 0
  scp1 = "scp " + imgpath + " ."
  scp2 = "scp ./" + flavor + " "+MACHINE+":" + LOC_IMG
  system (scp1)
  system (scp2)

  conn = libvirt.open ('remote+ssh://'+MACHINE+'/system') #this path shud be selected by some algo
  if conn == None:
    print 'Connection to remote machine failed!'
    return 0
  xmlOut = conn.getCapabilities()
  emulatorLoc = xmlOut.split("emulator>");
  emulatorLoc = emulatorLoc[1].split("<")[0];
  emulatorDom = xmlOut.split("<domain type='")
  emulatorDom = emulatorDom[1].split("'")[0]

  domXML="<domain type='qemu'><name>"+vmName+"</name><memory>"+str(vm['ram']*1024)+"</memory><vcpu>"+str(vm['cpu'])+"</vcpu><os><type arch='x86_64' machine='pc'>hvm</type><boot dev='hd'/></os><features><acpi/><apic/><pae/></features><on_poweroff>destroy</on_poweroff><on_reboot>restart</on_reboot><on_crash>restart</on_crash><devices><emulator>"+ emulatorLoc +"</emulator><disk type='file' device='disk'><driver name='"+ emulatorDom+"' type='raw'/><source file='"+ LOC_IMG + flavor  +"'/><target dev='hda' bus='ide'/><address type='drive' controller='0' bus='0' unit='0'/></disk></devices></domain>"

#  dom = conn.defineXML(domXML)
#  dom.create()

  dom = conn.createXML(domXML, 0) 
  domDic[vmID] = dom
  tempDic = {"vmid":vmID, "name":vmName, "vm_type":int(vm['tid']), "machine":MACHINE, "pmid":pmid, "ram":int(vm['ram']), "disk":int(vm['disk']), "cpu":int(vm['cpu'])}
  runningVM [vmID] = tempDic
  vmID += 1

  #print "domain " + vmName + " has been created"
  return vmID-1

def destroy (vmid):
  global runningVM
  global runningMachs
  global domDic

  if vmid not in runningVM:
    return 0

  tmp = runningVM[vmid]
  print "====================="
  print tmp
  print "====================="
  machname = tmp["machine"]
  print ">>>>>>>"
  print 'orig ram ', runningMachs[machname][1]
  print 'orig cpu ', runningMachs[machname][2]
  print ">>>>>>>"
  runningMachs[machname][1] += tmp["ram"]
  runningMachs[machname][2] += tmp["cpu"]
  print ">>>>>>>"
  print 'updated ram ', runningMachs[machname][1]
  print 'updated cpu ', runningMachs[machname][2]
  print ">>>>>>>"
  
  
  toDestroy = domDic[vmid]
  toDestroy.destroy()
  del domDic[vmid]
  del runningVM[vmid]
  return 1

    
def parse(rqst):
  global runningVM
  global runningMachs
  global mach_id_nam
  query = urlparse(rqst).query
  if len(query) ==  0:
    if rqst.find('types') >= 0:
      vmString = open (vm_type, 'r').read()
      dic = json.loads(vmString)
      return json.dumps(dic, indent=4)
    elif rqst.find('pm/list') >= 0:
      x = open (pm_file, 'r').read().split('\n')
      d = []
      for i in range(len(x)):
        if len(x[i]) == 0:
	  continue
        d.append(i+1)
      k = {}
      k["pmids"] = d
      return json.dumps(k, indent = 4)

    elif rqst.find("listvms") >= 0:
      pmidreq = int(rqst.split('/')[-2]) 
      l = []
      for i in runningVM:
        s = runningVM[i]
	if s["pmid"] == pmidreq:
          l.append(i)
      d = {}
      d["vmids"] = l
      return json.dumps(d, indent=4)

    elif rqst.find('pm/') >= 0:
      pmidreq = int(rqst.split('/')[-1])
      namm = mach_id_nam[pmidreq]
      d1 = {}
      d1["pmid"] = pmidreq
      cCPU = runningMachs[namm][9]
      cRAM = runningMachs[namm][8]
      fCPU = runningMachs[namm][2]
      fRAM = runningMachs[namm][1]
      dC = {}
      dC["cpu"] = cCPU
      dC["ram"] = cRAM
      dF = {}
      dF["cpu"] = fCPU
      dF["ram"] = fRAM
      d1["capacity"] = dC
      d1["free"] = dF
      return json.dumps(d1, indent=4)
    elif rqst.find ('image/list') >= 0:
      ff = open (image_file, 'r').read()
      f = ff.split('\n')
      x = 0
      kk = []
      for i in f:
        if i == '\n' or len(i) == 0:
	  continue
        name = i.split('/')[-1]
	d = {}
	d['id'] = x
	x += 1
	d['name'] = name
	kk.append(d)
      g = {}
      g['images'] = kk
      return json.dumps(g, indent=4)
    else:
      print 'certain types of rqsts still to handle'
  else:
    querydic = cgi.parse_qs(query)
    if rqst.find('create') >= 0:
      vmDescrip = getVMdesc(int(querydic['vm_type'][0]))
      vmName = str (querydic['name'][0])

      imgIndx = int (querydic['image_type'][0])
      allImgs = open (image_file, 'r').read()
      imgused = allImgs.split('\n')[imgIndx]

     # selectMachine() #it is stored in MACHINE
      id = create (vmDescrip, imgused, vmName)
      dic = {}
      dic["vmid"] = id
      return json.dumps(dic, indent=4)

    elif rqst.find('query') >= 0:
      vmid = int(querydic['vmid'][0])
      d = {}
      d[vmid] = runningVM[vmid]
      return json.dumps(runningVM[vmid],indent=4)
    elif rqst.find('destroy') >= 0:
      vmid = int (querydic['vmid'][0])
      x = destroy (vmid)
      dic = {}
      dic["status"] = x
      return json.dumps(dic, indent=4)
    else:
      print 'other cases still to handle'

####
class myHandler(BaseHTTPRequestHandler):
  def do_GET(self):
    self.send_response(200)
    self.send_header('Content-type', 'application/json')
    self.end_headers()
    result = parse(self.path)
    self.wfile.write (result)
    return


  
####
def main():
  pm_file = sys.argv[1]
  image_file = sys.argv[2]
  vm_type = sys.argv[3]

 # init()
  try:
    server = HTTPServer (('', PORT), myHandler)
    print 'Started httpserver on port: ', PORT
    server.serve_forever()

  except KeyboardInterrupt:
    print '^C recieved!! Shutting Down....ADIOS! :D'
    server.socket.close()

if __name__ == "__main__":
  main()
