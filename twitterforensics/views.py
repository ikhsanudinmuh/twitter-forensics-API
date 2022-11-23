from django.shortcuts import render
from requests import request
from django.template import loader
from django.http import HttpResponse, JsonResponse
import subprocess
import os
import re
import json
from urllib.parse import urlparse
from argparse import ArgumentParser
from django.views.decorators.csrf import csrf_exempt
import sqlite3

def index(request):
  if request.method == "GET":
    device = get_devices(request)
    context = {
      'devices': device
    }
    print('tes =>',context)

    html_template = loader.get_template('index.html')
    return HttpResponse(html_template.render(context, request), content_type='application/json')

def adb(args, device=None):
  base = ["D:/adb/adb.exe"]
  if device is not None:
    base = base + ['-s', device]

  args = base + args
  p = subprocess.Popen([str(arg) for arg in args], stdout=subprocess.PIPE)
  stdout, stderr = p.communicate()
  return (p.returncode, stdout, stderr)
  
def getprop(device, property, default):
  (rc, out, _) = adb(['shell', 'getprop', property], device=device)
  if not rc == 0:
    return default
  elif out.strip():
    return out.strip()
  else:
    return default
  
def getnetwork(device):
  print("Device Network ->", device)
  (rc, out, err) = adb(["shell", "dumpsys wifi | grep 'current SSID' | grep -o '{.*}'"], device=device)
  ore = out
  ore = ore.decode("utf-8")
  ore = ore.replace('=', ':')
  ore = ore.replace('iface', '"iface"')
  ore = ore.replace('"iface":', '"iface":"')
  ore = ore.replace(',ssid', '","ssid"')
  oreDict = json.loads(ore)

  print('network done ' + str(rc))
  if rc != 0:
    print(err)

  network = {
    'connected': True,
    'ssid': oreDict['ssid']
  }

  for l in out.split('\n'.encode("utf-8")):
    tokens = l.split()
    if not len(tokens) > 10 or tokens[0] != 'mNetworkInfo':
        continue
    print("Token 4:", tokens[4])
    print("Token 8:", tokens[8])
    network['connected'] = (tokens[4].startswith('CONNECTED/CONNECTED'.encode("utf-8")))
    network['ssid'] = tokens[8].replace('"'.encode("utf-8"), ''.encode("utf-8")).rstrip(','.encode("utf-8"))

  return network

def getbattery(device):
  (rc, out, err) = adb(['shell', 'dumpsys', 'battery'], device=device)
  print('battery done ' + str(rc))
  if rc != 0:
    print(err)

  battery = {
    'plugged': 0,
    'level': 0,
    'status': 1,
    'health': 1
  }

  for l in out.split('\n'.encode("utf-8")):
    tokens = l.split(': '.encode("utf-8"))
    if len(tokens) < 2:
      continue

    key = tokens[0].strip().lower()
    value = tokens[1].strip().lower()
    if key.decode('utf-8') == "ac powered" and value.decode('utf-8') == "true":
      battery['plugged'] = 'AC'
    elif key.decode('utf-8') == 'usb powered' and value.decode('utf-8') == 'true':
      battery['plugged'] = 'USB'
    elif key.decode('utf-8') == 'wireless powered' and value.decode('utf-8') == 'true':
      battery['plugged'] = 'Wireless'
    elif key.decode('utf-8') == 'level':
      battery['level'] = value
    elif key.decode('utf-8') == 'status':
      battery['status'] = value
    elif key.decode('utf-8') == 'health':
      battery['health'] = value
      
  return battery

def getscreen(device):
  (rc, out, err) = adb(['shell', 'dumpsys', 'input'], device=device)
  # print('screen done ' + str(rc))
  if rc != 0:
    print(err)

  screen = {
    'width': 0,
    'height': 0,
    'orientation': 0,
    'density': 0
  }

  for l in out.split('\n'.encode("utf-8")):
    tokens = l.split(': '.encode("utf-8"))
    if len(tokens) < 2:
      continue
    key = tokens[0].strip().lower()
    value = tokens[1].strip().lower()

    if key.decode('utf-8') == 'displaywidth':
      screen['width'] = value
    elif key.decode('utf-8') == 'displayheight':
      screen['height'] = value
    elif key.decode('utf-8') == 'orientation':
      screen['orientation'] = value

  (rc, out, err) = adb(['shell', 'wm', 'density'], device=device)
  tokens = out.split(': '.encode("utf-8"))
  if len(tokens) == 2:
    screen['density'] = tokens[1].strip()

  return screen

def get_logcat(request, id):
  if request.method == "GET":
    print(id)
    (rc, out, err) = adb(['logcat', '-d', '-v', 'brief'], device=id)
    print('logcat done ' + str(rc))

    if rc != 0:
      print(err)

    print("ini isi outnyaa: ", type(out))

    return HttpResponse(out.decode())
      
def get_devices(request):
  if request.method == "GET":
    (_, out, _) = adb(['devices'])

    devices = []
    for l in out.split('\n'.encode("utf-8")):
      tokens = l.split()
      if not len(tokens) == 2:
        # Discard line that doesn't contain device information
        continue

      id = tokens[0].decode('utf-8')
      devices.append({
        'id': id,
        'manufacturer': getprop(id, 'ro.product.manufacturer', 'unknown'),
        'model': getprop(id, 'ro.product.model', 'unknown'),
        'sdk': getprop(id, 'ro.build.version.sdk', 'unknown'),
        'timezone': getprop(id, 'persist.sys.timezone', 'unknown'),
        'product': getprop(id, 'ro.build.product', 'unknown'),
        'security_patch': getprop(id, 'ro.build.version.security_patch', 'unknown'),
        'api_level': getprop(id, 'ro.product.first_api_level', 'unknown'),
        'SELinux': getprop(id, 'ro.boot.selinux', 'unknown'),
        'operator': getprop(id, 'gsm.sim.operator.alpha', 'unknown'),
        # 'network': getnetwork(id),
        'battery': getbattery(id),
        'screen': getscreen(id)
      })

    content = devices
    # Stuff
    content[0]['manufacturer'] = content[0]['manufacturer'].decode('utf-8')
    content[0]['model'] = content[0]['model'].decode('utf-8')
    content[0]['sdk'] = content[0]['sdk'].decode('utf-8')
    content[0]['timezone'] = content[0]['timezone'].decode('utf-8')
    content[0]['product'] = content[0]['product'].decode('utf-8')
    content[0]['security_patch'] = content[0]['security_patch'].decode('utf-8')
    content[0]['api_level'] = content[0]['api_level'].decode('utf-8')
    content[0]['SELinux'] = content[0]['SELinux'].decode('utf-8')
    # content[0]['operator'] = content[0]['operator'].decode('utf-8')

    # Battery
    content[0]['battery']['level'] = content[0]['battery']['level'].decode('utf-8')
    content[0]['battery']['status'] = content[0]['battery']['status'].decode('utf-8')
    content[0]['battery']['health'] = content[0]['battery']['health'].decode('utf-8')

    # Screen
    content[0]['screen']['width'] = content[0]['screen']['width']
    content[0]['screen']['height'] = content[0]['screen']['height']
    content[0]['screen']['orientation'] = content[0]['screen']['orientation'].decode('utf-8')
    content[0]['screen']['density'] = content[0]['screen']['density'].decode('utf-8')

    print(content, "\n")

    return JsonResponse(content, safe=False)
  
# function pull and show data from twitter
def pullTwitter(request, id):
  if request.method == "GET":
    print("Device Twitter ->", id)
    notif = "&& echo '<br>\nCopy twitter package from root data: <code>success</code>\nMoved to sdcard folder: <code>success</code>\nCopy file to current directory: <code>success</code>\nExtract file: <code>success</code>'"
    (rc, out, err) = adb(["shell", "su 0 -c", "'cp -r /data/data/com.twitter.android /sdcard'", notif], device=id)
    (rc0, out0, err0) = adb(["shell", "cd /sdcard; tar -zcvf com.twitter.android.tar.gz com.twitter.android"], device=id)
    (rc1, out1, err1) = adb(["pull", "sdcard/com.twitter.android.tar.gz", "twitterforensics/data"], device=id)
    print(os.system("cd twitterforensics\data && tar -xvf com.twitter.android.tar.gz"))

    success = False;
    message = '';

    if rc != 0:
      print("RC Error", err)
      message = err;
    else:
      print("Copy twitter package from root data success")
      success = True;
      message = 'Copy twitter package from root data success';

    return JsonResponse({
      'success': success,
      'message' : message,
    }, safe=False)

def showTwitterChat(request, id):
    if request.method == "GET":
        (_, out, _) = adb(['devices'])
        serial = None
        for l in out.split('\n'.encode("utf-8")):
            tokens = l.split()
            if not len(tokens) == 2:
                # Discard line that doesn't contain device information
                continue
            serial = tokens[0].decode('utf-8')


        # Get users data at application
        foren_id = []
        global_db = sqlite3.connect(
            "D:/Kuliah/Semester 7/Forensik Digital/djangoproject/twitterforensics/data/com.twitter.android/databases/721493985282293760-63-versioncode-29653000.db")
        cur_global_db = global_db.cursor()
        cursor_global_db = cur_global_db.execute(
            "SELECT user_id as 'id', username as 'username', name as 'full_name' from users;")
        names_global_db = [description[0] for description in cursor_global_db.description]

        for i in cursor_global_db:
            Temp = {}
            for j in range(0, len(i)):
                Temp[names_global_db[j]] = i[j]
            foren_id.append(Temp)
        global_db.close()

        # Get detail of conversation
        id_versioncode_db = sqlite3.connect(
            "D:/Kuliah/Semester 7/Forensik Digital/djangoproject/twitterforensics/data/com.twitter.android/databases/721493985282293760-63-versioncode-29653000.db")
        cur_id_versioncode_db = id_versioncode_db.cursor()
        cursor_id_versioncode_db = cur_id_versioncode_db.execute(
            "SELECT conversation.conversation_entries_user_id as 'UserID', conversation.users_username as 'username', conversation.users_image_url as 'imageProfile', conversation.conversation_entries_data as 'chatData', dm_inbox.conversations_conversation_id as 'ContentID' FROM dm_inbox INNER JOIN conversation on dm_inbox.conversations_conversation_id = conversation.conversation_entries_conversation_id ORDER BY conversation._id;")
        names_id_versioncode_db = [description[0] for description in cursor_id_versioncode_db.description]
        id_versioncode = []

        Test = []
        count = 1
        for i in cursor_id_versioncode_db:
            Aho = {}
            Temp = {}  # {}
            TempTemp = {}  # ContentInfo:{}
            TempTempTemp = {}  # 1:{}
            for j in range(0, len(i)):

                # Only contentID
                if names_id_versioncode_db[j] == 'ContentID':
                    Temp[names_id_versioncode_db[j]] = i[j]
                    if i[j] not in [z['ContentID'] for z in id_versioncode]:
                        count = 1
                        Aho['ContentID'] = i[j]
                        Aho['ContentInfo'] = {}
                        Aho['ContentWith'] = ""
                        Aho['ContentWithUserID'] = ""
                        Aho['ContentWithUserFullName'] = ""
                        Test.append(Aho)
                        who = i[j].split('-')
                        for k in range(0, 2):
                            if who[k] == str(TempTemp['UserID']):
                                got = 1 if k == 0 else 0
                                TempTemp['fromID'] = int(who[k])
                                TempTemp['toID'] = int(who[got])
                        TempTempTemp[count] = TempTemp
                    elif i[j] in [z['ContentID'] for z in id_versioncode]:
                        count += 1
                        who = i[j].split('-')
                        for k in range(0, 2):
                            if who[k] == str(TempTemp['UserID']):
                                got = 1 if k == 0 else 0
                                TempTemp['fromID'] = int(who[k])
                                TempTemp['toID'] = int(who[got])
                        TempTempTemp[count] = TempTemp
                else:
                    if names_id_versioncode_db[j] == 'chatData':
                        TempTemp[names_id_versioncode_db[j]] = i[j].decode(encoding='utf-8', errors='ignore')
                    else:
                        TempTemp[names_id_versioncode_db[j]] = i[j]

            # Only contentInfo from 'else' above
            Temp['ContentInfo'] = TempTempTemp
            id_versioncode.append(Temp)

        id_versioncode_db.close()

        for i in range(0, len(Test)):
            who = Test[i]['ContentID'].split('-')
            Test[i]['ContentWithUserID'] = who[1]

            for l in range(0, len(foren_id)):
                if foren_id[l]['id'] == eval(Test[i]['ContentWithUserID']):
                    Test[i]['ContentWith'] = foren_id[l]['username']
                    Test[i]['ContentWithUserFullName'] = foren_id[l]['full_name']

            for j in range(0, len(id_versioncode)):
                if Test[i]['ContentID'] == id_versioncode[j]['ContentID']:
                    Test[i]['ContentInfo'].update(id_versioncode[j]['ContentInfo'])

        if serial == id:
            return JsonResponse(Test, safe=False)

def showTwitterUser(request, id) :
  if request.method == "GET":
    (_, out, _) = adb(['devices'])
    serial = None
    for l in out.split('\n'.encode("utf-8")):
      tokens = l.split()
      if not len(tokens) == 2:
        # Discard line that doesn't contain device information
        continue
      serial = tokens[0].decode('utf-8')


    # Get users data at application
    foren_id = []
    global_db = sqlite3.connect(
      "D:/Kuliah/Semester 7/Forensik Digital/djangoproject/twitterforensics/data/com.twitter.android/databases/721493985282293760-63-versioncode-29653000.db")
    cur_global_db = global_db.cursor()
    cursor_global_db = cur_global_db.execute(
      "SELECT user_id as 'id', username as 'username', name as 'full_name', followers, image_url from users LIMIT 50;")
    names_global_db = [description[0] for description in cursor_global_db.description]

    for i in cursor_global_db:
      Temp = {}
      for j in range(0, len(i)):
        Temp[names_global_db[j]] = i[j]
      foren_id.append(Temp)
    global_db.close()
    
    if serial == id :
      return JsonResponse(foren_id, safe=False)

@csrf_exempt
def post_shell(request):
  if request.method == "POST":
    rc, out, err = None, None, None
    payload = None
    for key, value in request.POST.items():
      payload = eval(key)
    if 'device' in payload and 'command' in payload:
      device = payload['device']
      command = payload['command']
      print(device + ' : ' + command)
      (rc, out, err) = adb(['shell', command], device=device)
      print('shell done ' + str(rc))

      if rc != 0:
        print(err)

    return HttpResponse(out.decode())

