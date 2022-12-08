import os
import random


class MidiFile:
    startSequence = [   [0x4D,0x54,0x68,0x64], #MThd
                        [0x4D,0x54,0x72,0x6B], #MTrk
                        [0xFF] #FF
                    ]
    
    typeDict = {0x00 : "Sequence Number",
                0x01 : "Text Event",
                0x02 : "Copyright Notice",
                0x03 : "Sequence/Track Name",
                0x04 : "Instrument Name",
                0x05 : "Lyric",
                0x06 : "Marker",
                0x07 : "Cue Point",
                0x20 : "MIDI Channel Prefix",
                0x2F : "End of Track",
                0x51 : "Set Tempo",
                0x54 : "SMTPE Offset",
                0x58 : "Time Signature",
                0x59 : "Key Signature",
                0x7F : "Sequencer-Specific Meta-event",
                0x21 : "Prefix Port",
                0x20 : "Prefix Channel",
                0x09 : "Other text format [0x09]",
                0x08 : "Other text format [0x08]",
                0x0A : "Other text format [0x0A]",
                0x0C : "Other text format [0x0C]"
                }

    
    def __init__(self,midi_file,verbose=False,debug=False):
        self.verbose = verbose
        self.debug = debug
        
        self.bytes = -1
        self.headerLength = -1
        self.headerOffset = 23
        self.format = -1
        self.tracks = -1
        self.division = -1
        self.divisionType = -1
        self.itr = 0
        self.runningStatus = -1
        self.tempo = 0
        
        self.midiRecord_list = []
        self.record_file = "midiRecord.txt"
        self.midi_file = midi_file
        
        self.deltaTimeStarted = False
        self.deltaTime = 0
        
        self.key_press_count = 0
        
        self.virtualPianoScale = list("1!2@34$5%6^78*9(0qQwWeErtTyYuiIoOpPasSdDfgGhHjJklLzZxcCvVbBnm")
        
        self.startCounter = [0] * len(MidiFile.startSequence)
        
        self.runningStatusSet = False
        
        self.events = []
        self.notes = []
        self.success = False
        
        print("Processing",midi_file)
        try:
            midi_path = os.getcwd() + "\\trebleMids\\" + self.midi_file
            with open(midi_path,"rb") as f:
                self.bytes = bytearray(f.read())
            self.readEvents()
            print(self.key_press_count,"notes processed")
            self.clean_notes()
            self.success = True
        finally:
            return
            
    
    def checkStartSequence(self):
        for i in range(len(self.startSequence)):
            if(len(self.startSequence[i]) == self.startCounter[i]):
                return True
        return False
    
    def skip(self,i):
        self.itr += i
    
    def readLength(self):
        contFlag = True
        length = 0
        while(contFlag):
            if((self.bytes[self.itr] & 0x80) >> 7 == 0x1):
                length = (length << 7) + (self.bytes[self.itr] & 0x7F)
            else:
                contFlag = False
                length = (length << 7) + (self.bytes[self.itr] & 0x7F)
            self.itr += 1
        return length
    
    def readMTrk(self):
        length = self.getInt(4)
        self.log("MTrk len",length)
        self.readMidiTrackEvent(length)
    
    def readMThd(self):
        self.headerLength = self.getInt(4)
        self.log("HeaderLength",self.headerLength)
        self.format = self.getInt(2)
        self.tracks = self.getInt(2)
        div = self.getInt(2)
        self.divisionType = (div & 0x8000) >> 16
        self.division = div & 0x7FFF
        self.log("Format %d\nTracks %d\nDivisionType %d\nDivision %d" % (self.format,self.tracks,self.divisionType,self.division))
    
    def readText(self,length):
        s = ""
        start = self.itr
        while(self.itr < length+start):
            s += chr(self.bytes[self.itr])
            self.itr+=1
        return s
    
    def readMidiMetaEvent(self,deltaT):
        type = self.bytes[self.itr]
        self.itr+=1
        length = self.readLength()
        
        try:
            eventName = self.typeDict[type]
        except:
            eventName = "Unknown Event " + str(type)
            
        self.log("MIDIMETAEVENT",eventName,"LENGTH",length,"DT",deltaT)
        if(type == 0x2F):
            self.log("END TRACK")
            self.itr += 2
            return False
        elif(type in [0x01,0x02,0x03,0x04,0x05,0x06,0x07,0x08,0x09,0x0A,0x0C]):
            self.log("\t",self.readText(length))
        elif(type == 0x51):
            tempo = round(60000000/self.getInt(3))
            self.tempo = tempo
            
            self.notes.append([(self.deltaTime/self.division),"tempo=" + str(tempo)])
            self.log("\tNew tempo is", str(tempo))
        else:
            self.itr+= length
        return True
        
    def readMidiTrackEvent(self,length):
        self.log("TRACKEVENT")
        self.deltaTime = 0
        start = self.itr
        continueFlag = True
        while(length > self.itr - start and continueFlag):
            deltaT= self.readLength()
            self.deltaTime += deltaT
            
            if(self.bytes[self.itr] == 0xFF):
                self.itr+= 1
                continueFlag = self.readMidiMetaEvent(deltaT)
            elif(self.bytes[self.itr] >= 0xF0 and self.bytes[self.itr] <= 0xF7):
                self.runningStatusSet = False
                self.runningStatus = -1
                self.log("RUNNING STATUS SET:","CLEARED")
            else:
                self.readVoiceEvent(deltaT)
        self.log("End of MTrk event, jumping from",self.itr,"to",start+length)
        self.itr = start+length
                
    def readVoiceEvent(self,deltaT):
        if(self.bytes[self.itr] < 0x80 and self.runningStatusSet):
            type = self.runningStatus
            channel = type & 0x0F
        else:
            type = self.bytes[self.itr]
            channel = self.bytes[self.itr] & 0x0F
            if(type >= 0x80 and type <= 0xF7):
                self.log("RUNNING STATUS SET:",hex(type))
                self.runningStatus = type
                self.runningStatusSet = True
            self.itr += 1
        
        if(type >> 4 == 0x9):
            #Key press
            key = self.bytes[self.itr]
            self.itr += 1
            velocity = self.bytes[self.itr]
            self.itr += 1
            
            map = key - 23 - 12 - 1
            while(map >= len(self.virtualPianoScale)):
                map -= 12
            while(map < 0):
                map += 12
            
            
            if(velocity == 0):
                #Spec defines velocity == 0 as an alternate notation for key release
                self.log(self.deltaTime/self.division,"~"+self.virtualPianoScale[map])
                self.notes.append([(self.deltaTime/self.division),"~"+self.virtualPianoScale[map]])
            else:
                #Real keypress
                self.log(self.deltaTime/self.division,self.virtualPianoScale[map])
                self.notes.append([(self.deltaTime/self.division),self.virtualPianoScale[map]])
                self.key_press_count += 1
                
        elif(type >> 4 == 0x8):
            #Key release
            key = self.bytes[self.itr]
            self.itr += 1
            velocity = self.bytes[self.itr]
            self.itr += 1
            
            map = key - 23 - 12 - 1
            while(map >= len(self.virtualPianoScale)):
                map -= 12
            while(map < 0):
                map += 12
            
            self.log(self.deltaTime/self.division,"~"+self.virtualPianoScale[map])
            self.notes.append([(self.deltaTime/self.division),"~"+self.virtualPianoScale[map]])
                
        elif(not type >> 4 in [0x8,0x9,0xA,0xB,0xD,0xE]):
            self.log("VoiceEvent",hex(type),hex(self.bytes[self.itr]),"DT",deltaT)
            self.itr +=1
        else:
            self.log("VoiceEvent",hex(type),hex(self.bytes[self.itr]),hex(self.bytes[self.itr+1]),"DT",deltaT)
            self.itr+=2
    
    def readEvents(self):
        while(self.itr+1 < len(self.bytes)):
            #Reset counters to 0
            for i in range(len(self.startCounter)):
                self.startCounter[i] = 0
                
            #Get to next event / MThd / MTrk
            while(self.itr+1 < len(self.bytes) and not self.checkStartSequence()):
                for i in range(len(self.startSequence)):
                    if(self.bytes[self.itr] == self.startSequence[i][self.startCounter[i]]):
                        self.startCounter[i] += 1
                    else:
                        self.startCounter[i] = 0
                        
                if(self.itr+1 < len(self.bytes)):
                    self.itr += 1
                        
                if(self.startCounter[0] == 4):
                    self.readMThd()
                elif(self.startCounter[1] == 4):
                    self.readMTrk()
    
    def log(self,*arg):
        if self.verbose or self.debug:
            for s in range(len(arg)):
                try:
                    print(str(arg[s]),end=" ")
                    self.midiRecord_list.append(str(arg[s]) + " ")
                except:
                    print("[?]",end=" ")
                    self.midiRecord_list.append("[?] ")
            print()
            if self.debug: input()
            self.midiRecord_list.append("\n")
        else:
            for s in range(len(arg)):
                try:
                    self.midiRecord_list.append(str(arg[s]) + " ")
                except:
                    self.midiRecord_list.append("[?] ")
            self.midiRecord_list.append("\n")
    
    def getInt(self,i):
        k = 0
        for n in self.bytes[self.itr:self.itr+i]:
            k = (k << 8) + n
        self.itr += i
        return k
        
    def round(i):
        up = int(i+1)
        down = int(i-1)
        if(up - i < i - down):
            return up
        else:
            return down
            
    def clean_notes(self):
        self.notes = sorted(self.notes, key=lambda x: float(x[0]))
        
        if(self.verbose):
            for x in self.notes:
                print(x)
        
        #Combine seperate lines with equal timings
        i = 0
        while(i < len(self.notes)-1):
            a_time,b_time = self.notes[i][0],self.notes[i+1][0]
            if (a_time == b_time):
                a_notes,b_notes = self.notes[i][1],self.notes[i+1][1]
                if "tempo" not in a_notes and "tempo" not in b_notes and "~" not in a_notes and "~" not in b_notes:
                    self.notes[i][1] += self.notes[i+1][1]
                    self.notes.pop(i+1)
                else:
                    i += 1
            else:
                i += 1

        #Remove duplicate notes on same line
        for q in range(len(self.notes)):
            letterDict = {}
            newline = []
            if not "tempo" in self.notes[q][1] and "~" not in self.notes[q][1]:
                for i in range(len(self.notes[q][1])):
                    if(not(self.notes[q][1][i] in letterDict)):
                        newline.append(self.notes[q][1][i])
                        letterDict[self.notes[q][1][i]] = True
                self.notes[q][1] = "".join(newline)
        return
        
    def save_song(self,song_file):
        print("Saving notes to",song_file)
        with open(song_file,"w") as f:
            f.write("playback_speed=1.0\n")
            for l in self.notes:
                f.write(str(l[0]) + " " + str(l[1]) + "\n")
        return
        
    def save_sheet(self,sheet_file):
        print("Saving sheets to",sheet_file)
        offset = self.notes[0][0]
        noteCount = 0
        with open(sheet_file,"w") as f:
            for timing,notes in self.notes:
                if not "tempo" in notes and "~" not in notes:
                    if(len(notes) > 1):
                        note = "["+notes+"]"
                    else:
                        note = notes
                    noteCount += 1
                    f.write("%7s " % note)
                    if(noteCount % 8 == 0):
                        f.write("\n")
        return
        
    def save_record(self,record_file):
        print("Saving processing log to",record_file)
        with open(record_file,"w") as f:
            for s in self.midiRecord_list:
                f.write(s)
        return
        
def get_file_choice():
    path = os.getcwd() + "\\trebleMids"
    fileList = os.listdir(path)
    #print(fileList)
    midList = []
    for f in fileList:
        if(".mid" in f or ".mid" in f.lower()):
            midList.append(f)
    print("\nType the number of a midi file press enter:\n")
    for i in range(len(midList)):
        print(i+1,":",midList[i])

    choice = int(input(">"))
    print()
    choice_index = int(choice)
    return midList[choice_index-1]

# to build, use "cd (playsong directory)"
# pyinstaller --onefile playSong.py

import keyboard
import threading
import sys
import math

global isPlaying
global infoTuple

sys.setrecursionlimit(10000)

owNotes = []
owTimes = []
isPlaying = False
storedIndex = 0
wait = 0
conversionCases = {'!': '1', '@': '2', '£': '3', '$': '4', '%': '5', '^': '6', '&': '7', '*': '8', '(': '9', ')': '0'}
white = {'1':0, '2':1, '3':2, '4':3, '5':4, '6':5, '7':6, '8':7, '9':8, '0':9, 'q':10, 'w':11, 'e':12, 'r':13, 't':14, 'y':15, 'u':16, 'i':17, 'o':18, 'p':19,
        'a':20, 's':21, 'd':22, 'f':23, 'g':24, 'h':25, 'j':26, 'k':27, 'l':28, 'z':29, 'x':30, 'c':31, 'v':32, 'b':33, 'n':34, 'm':35}
black = {'!':0, '@':1, '$':2, '%':3, '^':4, '*':5, '(':6, 'Q':7, 'W':8, 'E':9, 'T':10, 'Y':11, 'I':12, 'O':13, 'P':14, 'S':15, 'D':16, 'G':17, 'H':18, 'J':19,
        'L':20, 'Z':21, 'C':22, 'V':23, 'B':24}

song_file = "OW-Enem.txt"
f = open(song_file,"w")

key_delete = 'delete'
key_shift = 'shift'
key_end = 'end'
key_home = 'home'
    
def processFile():
    global playback_speed
    with open("song.txt","r") as macro_file:
        lines = macro_file.read().split("\n")
        tOffsetSet = False
        tOffset = 0
        playback_speed = float(lines[0].split("=")[1])
        print("Playback speed is set to %.2f" % playback_speed)
        tempo = 60/float(lines[1].split("=")[1])
        
        processedNotes = []
        
        for l in lines[1:]:
            l = l.split(" ")
            if(len(l) < 2):
                # print("INVALID LINE")
                continue
            
            waitToPress = float(l[0])
            notes = l[1]
            processedNotes.append([waitToPress,notes])
            if(not tOffsetSet):
                tOffset = waitToPress
                print("Start time offset =",tOffset)
                tOffsetSet = True

    return [tempo,tOffset,processedNotes]

def floorToZero(i):
    if(i > 0):
        return i
    else:
        return 0

# for this method, we instead use delays as l[0] and work using indexes with delays instead of time
# we'll use recursion and threading to press keys
def parseInfo():
    global owNotes
    global owTimes

    owNotes = []
    owTimes = []
    prevTime = 0

    tempo = infoTuple[0]
    notes = infoTuple[2][1:]
    
    # parse time between each note
    # while loop is required because we are editing the array as we go
    i = 0
    while i <= len(notes)-1:
        note = notes[i]
        if i != len(notes) - 1:
            nextNote = notes[i+1]
        if "tempo" in note[1]:
            tempo = 60/float(note[1].split("=")[1])
            notes.pop(i)

            note = notes[i]
            if i < len(notes)-1:
                nextNote = notes[i+1]
        else:
            if(not('~' in infoTuple[2][i][1]) and not('tempo' in infoTuple[2][i][1])):
                # print("i: " + str(i))
                # print("tuple: " + str(infoTuple[2][i][1]))
                # print("wait: " + str(infoTuple[2][i][0]))
                owNotes.append(infoTuple[2][i][1])
                owTimes.append((infoTuple[2][i][0] - prevTime) * tempo)
                prevTime = infoTuple[2][i][0]
            #note[0] = (nextNote[0] - note[0]) * tempo
            i += 1

    # let's just hold the last note for 1 second because we have no data on it
    notes[len(notes)-1][0] = 1.00

    return notes

def getPosition(time, last):
    #print(time)
    if last == -1 or time > 0.6:
        x = round(random.uniform(-95.5, -85.5), 2)
        y = round(random.uniform(10.70, 14.00), 2)
        z = round(random.uniform(-46.12, -35.12), 2)
        string = "Vector(" + str(x) + ", " +str(y)+ ", " + str(z) + ")"
    else:
        #print("last: " + str(last))
        if random.randint(0, 1) == 1:
            x = float(last.split("(")[1].split(',')[0]) + (random.uniform(-4, -2))*time*2
            if x < -96:
                x = float(last.split("(")[1].split(',')[0]) + random.uniform(2, 4)*time*2
        else:
            x = float(last.split("(")[1].split(',')[0]) + (random.uniform(2, 4))*time*2
            if x > -85:
                x = float(last.split("(")[1].split(',')[0]) + (random.uniform(-4, -2))*time*2
        if random.randint(0, 1) == 1:
            y = float(last.split(" ")[1].split(',')[0]) + (random.uniform(0.5, 1.5))*time*2
            if y > 14:
                y = float(last.split(" ")[1].split(',')[0]) + (random.uniform(-1.5, -0.5))*time*2
        else:
            y = float(last.split(" ")[1].split(',')[0]) + (random.uniform(-1.5, -0.5))*time*2
            if y < 10:
                y = float(last.split(" ")[1].split(',')[0]) + (random.uniform(0.5, 1.5))*time*2
        if random.randint(0, 1) == 1:
            z = float(last.split(" ")[2].split(')')[0]) + (random.uniform(-4, -2))*time*2
            if z < -46:
                z = float(last.split(" ")[2].split(')')[0]) + (random.uniform(2, 4))*time*2
        else:
            z = float(last.split(" ")[2].split(')')[0]) + (random.uniform(2, 4))*time*2
            if z > -35:
                z = float(last.split(" ")[2].split(')')[0]) + (random.uniform(-4, -2))*time*2
        #print("Vector(" + str(x) + ", " +str(y)+ ", " + str(z) + ")")
        string = "Vector(" + str(x) + ", " +str(y)+ ", " + str(z) + ")"
    return (string)

def createOW():
    global storedIndex
    global owTimes
    global owNotes

    pos = -1 
    x = 0
    #print(owNotes)
    #print(owTimes)

    while x <= math.floor(len(owNotes) / 100):
        f.write("rule(\"ENEMY PART " + str(x) + "\")\n{\n\tevent\n\t{\n\t\tOngoing - Global;\n\t}\n\n\tactions\n\t{\n")
        for y in range(0, 100):
            if y + (x)*100 < len(owNotes):
                note = owNotes[y + (x-1)*100 - 1]
                pos = getPosition(owTimes[y + (x)*100], pos)
                if y % 100 == 99 or y % 100 == 49:
                    f.write("\t\tModify Global Variable (enemTime, Append To Array, %2.4f);\n" % (float(owTimes[y + (x)*100]) - 0.033))
                else:
                    f.write("\t\tModify Global Variable (enemTime, Append To Array, %2.4f);\n" % owTimes[y + (x)*100])
                f.write("\t\tModify Global Variable (enemPos, Append To Array, " + pos + ");\n")
            if(y + (x)*100 == len(owNotes)):
                f.write("\t\tGlobal.numEnems = " + str(len(owNotes)) + ";\n")
        #print(y + (x)*100)
        f.write("\t}\n}\n\n")
        x += 1
    return
    
def main():
    import sys

    global isPlaying
    global infoTuple
    global playback_speed
    global owTimes
    global owNotes

    if len(sys.argv) > 1:
        midi_file = sys.argv[1]
        if not os.path.exists(midi_file):
            print(f"Error: file not found '{midi_file}'")
            return 1
            
        if(not (".mid" in midi_file or ".mid" in midi_file.lower())):
            print(f"'{midi_file}' has an inccorect file extension")
            print("make sure this file ends in '.mid'")
            return 1
    else:
        midi_file = get_file_choice()
    
    try:
        midi = MidiFile(midi_file)
    except Exception as e:
        print("An error has occured during processing::\n\n")
        raise e
        return 1
    
    song_file = "song.txt"
    
    midi.save_song(song_file)

    infoTuple = processFile()
    infoTuple[2] = parseInfo()
    createOW()

    return 0
                
if __name__ == "__main__":
    main()
