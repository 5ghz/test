import sys
import paramiko
import getopt
import pushy

inputfile='input.txt'
inputkeyfile='key.txt'
keylist = []
try:
   opts, args = getopt.getopt(sys.argv[1:],"i:k:h",["ifile=","ikfile=",'help'])
except getopt.GetoptError:
   print 'main.py -i <input file> -k <input key file>'
   sys.exit(2)

for opt, arg in opts:
   print opt
   if opt in ("-h", "--help"):
      print 'main.py -i <input file> -k <input key file>'
      sys.exit()
   elif opt in ("-i", "--ifile"):
      inputfile = arg
   elif opt in ("-k", "--ikfile"):
      inputkeyfile = arg

try:
   inputkeyfiledata = open(inputkeyfile)
   for key_record in inputkeyfiledata:
      key_record = key_record.rstrip('\n')
      keylist.append(key_record)

except IOError as e:
   print(e)
   sys.exit(2)

try:
   inputfiledata = open(inputfile)
except IOError as e:
   print(e)
   sys.exit(2)

for host_record in inputfiledata:
    host_dict = dict( (n,v) for n,v in (a.split('=') for a in host_record.split()) )
    ssh_host=host_dict.get("host","127.0.0.1")
    ssh_pass=host_dict.get("password","qwerty")
    ssh_user=host_dict.get("user","root")
    ssh_port=host_dict.get("port",22)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
#    print ssh_host, ssh_pass, ssh_user, ssh_port
    ssh.connect(ssh_host,port=int(ssh_port) ,username=ssh_user,password=ssh_pass)
    conn = pushy.connect("ssh:"+ssh_host,  username=ssh_user, password=ssh_pass,port=int(ssh_port),missing_host_key_policy="autoadd")
    myarray = {}
    userlist = []
    userhome = []
    sources = {}
    userkey = {}
    sftp_client = ssh.open_sftp()

    remote_file = sftp_client.open('/etc/ssh/sshd_config')
    try:
       for line in remote_file:
           if not (re.findall(r'^#', line)) and not (re.findall(r'^$', line)):
               line = line.rstrip('\n')
               key = re.split(' |\t',line,1)[0]
               value = re.split(' |\t',line,1)[1]
               myarray[key] = value
    finally:
       remote_file.close()
    allowusers=''
    allowgroups=''
    passauth=0 
    firewall=1

    if 'PasswordAuthentication' in myarray:
       if myarray['PasswordAuthentication']=='yes':
           passauth=1
    if 'AllowUsers' in myarray:
       allowusers=myarray['AllowUsers']

    try:
       remote_bus = conn.modules.dbus.SystemBus()
    except ImportError:
       firewall=0
    if firewall:
       remote_data = remote_bus.get_object('org.fedoraproject.FirewallD1', '/org/fedoraproject/FirewallD1')
       remote_zones = remote_data.getActiveZones()
       for zone in remote_zones:
           if zone == 'drop' or zone == 'block':
              continue
           services = remote_data.getServices(zone)
           sources = remote_data.getSources(zone)
           if 'ssh' in services and zone == 'public':
              sources = '0.0.0.0/0'
              break
           if 'ssh' in services:
              sources += remote_data.getSources(zone)

    remote_users=conn.modules.pwd.getpwall()

    for user in remote_users:
       if user[2] > 999 and user[0] != "nobody":
           userlist.append(user[0])
           userhome.append(user[5])
       if user[0] == "root":
           userlist.append(user[0])
           userhome.append(user[5])

    for home in userhome:
       homekeys = home + '/.ssh/authorized_keys'
       if conn.modules.os.path.isfile(homekeys):
           key_sftp_client = ssh.open_sftp()
           try:
              key_remote_file = key_sftp_client.open(homekeys)
              remote_data = key_remote_file.read()

              for key_record in keylist:
                  key_record = key_record.rstrip('\n')
                  keyfile = open(key_record)
              if keyfile.read() in remote_data:
                      userkey[userlist[userhome.index(home)]] = key_record
           finally:
              key_remote_file.close()

    if passauth:
       for iuser in userlist:
           if iuser in allowusers:
              if iuser in userkey:
                  print ssh_host, iuser, sources, userkey[iuser]
              else:
                  print ssh_host, iuser, sources, "no key"
    else:
       for iuser in userlist:
           if iuser in allowusers:
              if iuser in userkey:
                 print ssh_host, iuser, sources, userkey[iuser]
    conn.close()
    ssh.close()
