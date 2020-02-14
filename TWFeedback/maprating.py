# DPLib - Asynchronous bot framework for Digital Paint: Paintball 2 servers
# Copyright (C) 2017  MichaÅ‚ Rokita
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either map_version 3 of the License, or
# (at your option) any later map_version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Ranking system

from dplib.server import Server
from shutil import copyfile
import os
import time
import threading

s = Server(hostname='127.0.0.1', port=22222,
           logfile=r'/home/paintball/paintball2/pball/qconsole22222.log',
           rcon_password='whoaisbest')
           
           
def add_feedback(feedback, nick, good):
    players=s.get_players()
    #### Retrieve player's ID ###
    playerid = 0
    for player in players:
        if player.nick == nick:
            playerid=player.dplogin
            break
    
    ### Define hostname specific file paths ###
    status = s.get_status()
    servername=status.get("hostname")
    mapname=status.get("map_name")
    ratefilename = "/var/www/html/whoa.ga/maprating-"+servername+".txt"    
    playersfilename = "/var/www/html/whoa.ga/mapplayers-"+servername+".txt" 
    reasonfilename = "/var/www/html/whoa.ga/mapfeedback-"+servername+".txt"
    
    ### Check if player already voted on that specific map_name ###
    alreadyvoted=False
    if os.path.exists(playersfilename):
        f=open(playersfilename, "r")
        for line in f:
            if line.startswith(mapname):
                line=line.replace(mapname+" ","")
                line=line.split("\n")
                if line[0] == playerid:
                    alreadyvoted=True
        f.close()
    
    ### If not, add player's ID to playersfilename and vote+reason to reasonfilename with the map_name ###
    if not alreadyvoted:
        f=open(playersfilename, "a")
        f.write(mapname+" "+playerid+"\n")
        f.close()
        if os.path.exists(reasonfilename):
            append_write = 'a' # append if already exists
        else:
            append_write = 'w' # make a new file if not
        with open(reasonfilename ,append_write) as myfile:
            if(good):
                myfile.write(mapname+" "+"+ "+nick+": "+feedback + "\n")
            else:
                myfile.write(mapname+" "+"- "+nick+": "+feedback + "\n")
    
    ### If yes, replace player's previous vote+reason with his latest one and map_name ###
    if alreadyvoted:
        f=open(reasonfilename, "r")
        for lines in f:
            if lines.startswith(mapname):
                line=lines.replace(mapname+" ","")
                line = line.replace("+ ","")
                line = line.replace("- ","")
                if line.startswith(nick):
                    if(good):
                        replaceline("/var/www/html/whoa.ga/mapfeedback-"+servername, lines, mapname+" "+"+ "+nick+": "+feedback + "\n")
                    else:
                        replaceline("/var/www/html/whoa.ga/mapfeedback-"+servername, lines, mapname+" "+"- "+nick+": "+feedback + "\n")
        f.close()
        
    ### Count + and - votes to calculate consensus percentage and add mapspecifically to maprate file ###
    f=open(reasonfilename, "r")
    pro=0
    con=0
    total=0
    for line in f:
        total+=1
        if line.startswith("+"):
            pro += 1
        elif line.startswith("-"):
            con += 1
    f.close()
    percentage=0
    if not total==0:
        percentage=pro/total*100
    else: # test2
        percentage=-1
    f=open(ratefilename, "r")
    alreadyrated=False
    for lines in f:
        if lines.startswith(mapname):
            alreadyrated=True
            replaceline("/var/www/html/whoa.ga/maprating-"+servername, lines, mapname+" "+str(round(percentage,4)))
    f.close()
    if not alreadyrated:
        f=open(ratefilename, "w")
        f.write(mapname+" "+str(round(percentage,4)))
        f.close()
    s.say("{C}9***{C}CThank you for your vote, "+mapname+" now stands at "+str(round(percentage,4)) +"% !{C}9***")
   
def replaceline(path, oldcontent, newcontent):
    copyfile(path+".txt", path+"tmp.txt")
    g=open(path+".txt", "w")
    #with os.fdopen(path+".txt", "w") as new_file:
    with open(path+"tmp.txt") as old_file:
        for line in old_file:
            if(line == oldcontent):
                g.write(newcontent)
            else:
                g.write(line)
    g.close()
    os.remove(path+"tmp.txt")

@s.event
def on_chat(nick, message):
    if message.startswith('!badmap'):
        add_feedback(message.replace("!badmap",""), nick, False)
    elif message.startswith('!goodmap'):
        add_feedback(message.replace("!goodmap",""), nick, True)

def infomessage():
    s.say("{C}0***{C}EDo you like this map_name? type '!goodmap <reason>' if you do, or '!badmap <reason>' if you dont!{C}0***")
    t = threading.Timer(300.0, infomessage,())
    t.start()

t = threading.Timer(180.0, infomessage,())
t.start()
    
s.run()
