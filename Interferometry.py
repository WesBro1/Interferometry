#Created by Wesley Brouwer (5144981)
#This script was created for the data processing of interferometry. The script can actually record data itself or data can be uploaded to it.

#A lot of imports need to be used. Some of them are not standard and first have to be installed using anaconda powershell.


import numpy as np
from tkinter import *
from tkinter import filedialog
import os
from pydub import AudioSegment
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import time
import pyaudio
import wave
import xlsxwriter
import winsound

#The following classes are for the interactive windows and data processing. I decided to change a few things half way,
#however I thought it would be too time consuming to change everything after those changes. Thus this script is far
#from beautiful. I have not error proved execution mode completely, since I mainly used library mode for collecting my data.
#Thus although execution mode has a few great features, they may cause an error.
#The GUI does not like it if you close a window which is processing.
#If there is an error on the other hand, you can actually press the cross and reopen that window from the main menu.

#The first few classes contain both the math and how the data was stored.

#all filters use functions return V(f)*f
def low_pass_filter(f, f_3, f_4): 
    filt = []
    for elem in f:
        if elem<=f_3:
            filt.append(elem)
        elif elem>=f_4:
            filt.append(0.0)
        else:
            e = np.pi/2*(elem-f_3)/(f_4-f_3)
            if e <= -np.pi/2 or e>=np.pi/2:
                filt.append(0.0)
            else:
                filt.append(elem*np.math.cos(e)**2)       
    return np.array(filt)

def high_pass_filter(f, f_1, f_2):
    filt = []
    for elem in f:
        if elem<=f_1:
            filt.append(0.0)
        elif elem>=f_2:
            filt.append(elem)
        else:
            e = np.pi/2*(elem-f_1)/(f_2-f_1)
            if e <= -np.pi/2 or e>=np.pi/2:
                filt.append(elem)
            else:
                filt.append(elem*np.math.sin(e)**2)  
    return np.array(filt)

def band_pass_filter(f, f_1, f_2, f_3, f_4):
    return high_pass_filter(low_pass_filter(f, f_3, f_4), f_1, f_2)

def normalized_cross_corelation(tau, s_m, s_ref): 
    if tau>= 0: #according to bracewell a negative tau is the same as interchanging them
        l = min(s_m.size-tau,s_ref.size)
        s_m_n = s_m[tau:l+tau]/2**16 #value returned by dotproduct is max 2byte (thus we have to normalize otherwise np.dot() overflows and returns a lower number)
        s_ref_n = s_ref[:l]/2**16 #value returned by dotproduct is max 2byte (thus we have to normalize)
        b_left = np.linalg.norm(s_m_n) #calculates bottom left part
        b_right = np.linalg.norm(s_ref_n) #calculates bottom right part
        if b_right >0 and b_left >0: #If either has a norm of zero, zero has to be returned
            top = np.vdot(s_m_n,s_ref_n) #calculates top of fraction
            return top/(b_left*b_right)
        else:
            return 0.0
    else:
        return normalized_cross_corelation(abs(tau),s_ref,s_m)      

def max_cross_corelation(s_m,s_ref):
    l = min(s_m.size,s_ref.size)-1
    if np.array_equal(s_m[:l],s_ref[:l]): #checks if they are equal, which saves time if they are.
        return 1
    else:
        min_elem = int(l//2) #Since I modify all audio this is my personal choice. 
        l = l -min_elem
        return max(map(lambda tau: normalized_cross_corelation(tau, s_m, s_ref), range(-l,l,1)))
    
class library_data():
    def __init__(self):
        self.length = int(0)
        self.nodes = {}
        self.samp = int(0)
        self.libar = np.array([])
    
    def add_node (self, nodefile):
        n= self.length
        try:
            self.length+=1
            name = str(simpledialog.askstring("Name for library node", "What library node:" + str(nodefile)))
            samp = self.samp
            self.nodes[self.length] = data_node(name, samp)
            self.nodes[self.length].file(nodefile)
            if self.samp == 0:
                self.samp = self.nodes[self.length].samp
        except:
            self.length = n
            messagebox.showwarning(title = None, message = "Error: file not found or other I/O error. (DECODING FAILED)")
    
    #def add_lib (self, nodefile):
        #self.lib_array()
        #return
        #split the nodefile into different node data
    
    def delta(self):
        return 1/self.samp
        
    def lib_array(self):
        if self.length>= 1:
            self.libar = np.zeros(shape = (self.length,self.length))
            for i in range(self.length):
                for j in range (i, self.length):
                    if i == j:
                        self.libar[i,j] = 1
                    else:
                        self.libar[i,j] = max_cross_corelation(self.nodes[i+1].s, self.nodes[j+1].s)
                        self.libar[j,i] = self.libar[i,j]
        
    def update_lib_array(self):
        new_column = np.zeros(shape = ((self.length-1),1))
        new_row = np.zeros(shape = (1, self.length))
        for i in range (self.length-1):
            cross = max_cross_corelation(self.nodes[i+1].s, self.nodes[self.length].s)
            new_column[i,0] = cross
            new_row[0,i] = cross
        new_row[0,self.length-1] = 1.0
        self.libar = np.append(self.libar, new_column, axis=1)
        self.libar = np.append(self.libar, new_row, axis=0)
           
    def remove_node(self, val):
        try:
            val = int(val)
            if val >=1 and val <=self.length:
                if self.length >= 2:
                    name = self.nodes[val].name
                    for i in range(val, self.length):
                        self.nodes[i] = self.nodes[i+1]
                    self.nodes[self.length] = None
                    self.length -= 1
                    self.libar = np.delete(np.delete(self.libar,val-1,0),val-1,1)
                    messagebox.showwarning(title=None, message="Library node: " + str(val) + " with name " + str(name) + " has been removed")
                else:
                    self.length = 0
                    name = self.nodes[val].name
                    self.nodes[val] = None
                    self.libar = np.array([])
                    self.samp = 0
                    messagebox.showwarning(title=None, message="Library node: " + str(val) + " with name " + str(name) + " has been removed. Library is now empty.")
            else:
                messagebox.showwarning(title=None, message="Input in entry does not correspond to a library node")
        except:
            d = 0
            for i in range (self.length):
                if val == self.nodes[i+1].name:
                    d = i+1
            self.remove_node(d)
    
    def change_node_name(self, val):
        try:
            val = int(val)
            if val >=1 and val <=self.length:
                name = self.nodes[val].name
                new_name = self.nodes[val].change_name()
                messagebox.showwarning(title=None, message="Library node: " + str(val) + " with old name " + str(name) + " has been changed to:" + str(self.nodes[val].name))
                return val, new_name
            else:
                messagebox.showwarning(title=None, message="Input in entry does not correspond to a library node")
                return False, False
        except:
            d = 0
            for i in range (self.length):
                if val == self.nodes[i+1].name:
                    d = i+1
            return self.change_node_name(d)

    def remove_library(self):
        for i in range(1,self.length+1):
            self.nodes[i] = None
        self.nodes = {}
        self.length = int(0)
        self.samp = 0
        self.libar = np.array([])            
        
    def filter_lib(self, value, f_1, f_2, f_3, f_4):
        for i in range(self.length):
            self.nodes[i+1].after_filter(value, f_1, f_2, f_3, f_4)
    
    def compare_to_library(self, measured_node):
        compare = np.zeros(self.length)
        for i in range(self.length):
            compare[i] = max_cross_corelation(measured_node.s, self.nodes[i+1].s)
        return compare
    
    def continuous_param(self):
        m = 0
        for i in range(self.length):
            m = min(self.nodes[i+1].s.size, m)
        return m
        
    def continuous_compare(self, array, l, m, chunk, minimum):
        cross = []
        stat = False
        for i in range(self.length):
            if l>m:
                k = max(map(lambda tau: normalized_cross_corelation(tau, np.array(array), self.nodes[i+1].dar), range(l-m,l-m+chunk)))
            else:
                k = max(map(lambda tau: normalized_cross_corelation(tau, np.array(array), self.nodes[i+1].dar), range(0,chunk)))
            cross.append(k)
            if k>minimum:
                stat = i+1
        if stat:
            return self.nodes[stat].name
        else:
            return stat
        
    def frequency_bounds(self):
        f_low = None
        f_high = None
        for i in range(self.length):
            f_1, f_2 = self.nodes[i+1].get_h_l_frequency()
            if i == 0:
                f_low = f_1
                f_high = f_2
            else:
                f_low = max(f_1, f_low)
                f_high = min (f_2, f_high)
        return f_low, f_high

class data_node(object):
    def __init__(self,  name, samp):
        self.name = name
        self.samp = samp
        
    def file(self, nodefile):
        seg = AudioSegment.from_file(nodefile)
        fsamp = seg.frame_rate
        if self.samp != 0 and fsamp!= self.samp:
            seg.set_frame_rate(self.samp)
        if self.samp == 0:
            self.samp = fsamp
        ar = np.array(seg.get_array_of_samples())
        i = 0
        stop = ar.size
        while(ar[i] == 0 and stop>=i+1):
            i += 1
        j = stop-1
        while(ar[j] == 0 and j>0):
            j -= 1
        if i >= j:
            i = 0
            j = min(stop, 5000)
        self.dar = ar[i:j]
        self.s = self.dar
    
    def modify(self, begin, end):
        self.dar = self.dar[begin:end]
        self.s = self.dar
    
    def array(self, array, fsamp):
        if self.samp != 0 and fsamp!= self.samp:
            seg = AudioSegment.from_numpy_array(array,fsamp)
            seg.set_frame_rate(self.samp)
            array = np.array(seg.get_array_of_samples())
        i = 0
        stop = array.size
        while(ar[i] == 0 and stop>=i+1):
            i += 1
        j = stop-1
        while(ar[j] == 0 and j>0):
            j -= 1
        if i >= j:
            i = 0
            j = min(stop, 5000)
        self.dar = ar[i:j]
        self.s = np.array(self.dar)

    def after_filter(self, val, f_1, f_2, f_3, f_4):
        if val == 1 or (f_1 == f_2 == f_3 == f_4 == 0):
            self.s = np.array(self.dar)
        else:
            ampspectrum=np.absolute(np.fft.rfft(self.dar))
            if val == 2:
                fil_fft = low_pass_filter(ampspectrum, f_3, f_4)
                self.s = np.fft.irfft(fil_fft)
            elif val == 3:
                fil_fft = high_pass_filter(ampspectrum, f_1, f_2)
                self.s = np.fft.irfft(fil_fft)
            elif val == 4:
                fil_fft = band_pass_filter(ampspectrum, f_1, f_2, f_3, f_4)
                self.s = np.fft.irfft(fil_fft)  
    
    def change_name(self):
        self.name = str(simpledialog.askstring("Name for library node", "What library node:"))
        return self.name
    
    def get_h_l_frequency(self):
        ampspectrum=np.fft.rfft(self.dar)
        return np.amin(ampspectrum), np.amax(ampspectrum)
    
#All classes from here on are the interactive menu and its functions.
      
class mod_window(object):
    def __init__(self, master, array):
        self.top=Toplevel(master) 
        self.top.title("Modify data node")
        self.top.geometry('600x800') 
        
        self.l = array.size
        self.begin = 0
        self.end = self.l
        
        fig = Figure(figsize=(6,6))
        a = fig.add_subplot(111)
        a.plot(array,color='blue')

        a.set_title ("Visualization of array", fontsize=16)
        a.set_ylabel("Amplitude", fontsize=14)
        a.set_xlabel("Sample", fontsize=14)

        self.frame1 = Frame(self.top)
        self.frame1.pack(side = "top")

        canvas = FigureCanvasTkAgg(fig, self.frame1)
        canvas.get_tk_widget().pack()
        
        self.frame2 = Frame(self.top)
        self.frame2.pack(side = "bottom")
        self.b1=Button(self.frame2,text='Adjust',command=lambda : self.adjust(array))
        self.b1.pack(side = "right")
        
        self.frame2top = Frame(self.frame2)
        self.frame2top.pack(side = "top")
        self.e1=Entry(self.frame2top)
        self.e1.insert(END, self.begin)
        self.e1.pack(side = "left")
        self.e2=Entry(self.frame2top)
        self.e2.insert(END, self.end)
        self.e2.pack()
        
        
        self.frame2bot = Frame(self.frame2)
        self.frame2bot.pack(side = "bottom")
        self.b = Button(self.frame2bot,text='Ok',command=lambda : self.top.destroy())
        self.b.pack()
    
    def adjust(self, array):
        try:
            self.begin = int(self.e1.get())
            self.end = int(self.e2.get())
            if self.end > self.l:
                self.end = self.l
            if self.begin < 0:
                self.begin = 0
        except:
            messagebox.showwarning(title=None, message="Input invalid")
        fig = Figure(figsize=(6,6))
        a = fig.add_subplot(111)
        a.plot(range(self.l),array,color='black')
        a.plot(range(self.begin,self.end),array[self.begin:self.end],color = 'blue')

        a.set_title ("Visualization of array", fontsize=16)
        a.set_ylabel("Amplitude", fontsize=14)
        a.set_xlabel("Sample", fontsize=14)

        self.frame1.destroy()
        self.frame1 = Frame(self.top)
        self.frame1.pack(side = "top")

        canvas = FigureCanvasTkAgg(fig, self.frame1)
        canvas.get_tk_widget().pack()    
    
class single_record(object):
    def __init__(self, master):
        self.filename = None
        self.top=Toplevel(master) 
        self.top.title("Record single data node")
        self.top.geometry('800x400') 
        
        self.frame1 = Frame(self.top)
        self.frame1.pack(side = "top")
        
        self.frame2 = Frame(self.frame1)
        self.frame2.pack(side = "top")
        self.l1= Label(self.frame2, text="Start recording after how many seconds: ")
        self.l1.pack(side = "top")
        self.e1=Entry(self.frame2)
        self.e1.insert(END, 12.00)
        self.e1.pack(side = "bottom")
        
        self.frame3 = Frame(self.frame1)
        self.frame3.pack(side = "bottom")
        self.l1= Label(self.frame3, text="Maximum record time in seconds:")
        self.l1.pack(side = "top")
        self.e2=Entry(self.frame3)
        self.e2.insert(END, 4.00)
        self.e2.pack(side = "bottom")
        
        self.frame4 = Frame(self.top)
        self.frame4.pack()
        self.b1=Button(self.frame4,text='Record',command=lambda : self.record(master))
        self.b1.pack()
        
        self.b = Button(self.top,text='Close window',command=lambda : self.top.destroy())
        self.b.pack(side = "bottom")
    
    def timer(self):
        self.b["state"] = "disabled"
        try:
            t = float(self.e1.get())
            max_t = float(self.e2.get())
            if t < 0.0:
                t = 3.0
            if max_t <0.0:
                max_t = 4.0
        except:
            messagebox.showwarning(title=None, message="One of the inserted values could not be converted to a float.")
            return 5.0
        
        frequency = 2500  # Set Frequency To 2500 Hertz
        duration = 100  # Set Duration To 100 ms == 0.1 second
        
        while t>0.0: 
            winsound.Beep(frequency, duration)
            time.sleep(0.9)
            t -= 1.0
        self.top.l9 = Label(self.top, text = "Start")
        self.top.l9.pack()
        return max_t
    
    def record(self, master):
        max_t = self.timer()
        chunk = 1024  # Record in chunks of 1024 samples
        sample_format = pyaudio.paInt16  # 16 bits per sample
        channels = 1
        fs = master.lib_dat.samp
        if fs == 0:
            fs = 44100  # Record at 44100 samples per second
        p = pyaudio.PyAudio()  # Create an interface to PortAudio
        stream = p.open(format=sample_format,
                channels=channels,
                rate=fs,
                frames_per_buffer=chunk,
                input=True)

        frames = []  # Initialize array to store frames

        # Store data in chunks for max_t seconds
        for i in range(0, int(fs / chunk * max_t)):
            data = stream.read(chunk)
            frames.append(data)

        # Stop and close the stream 
        stream.stop_stream()
        stream.close()
        # Terminate the PortAudio interface
        p.terminate()
        
        #save as file
        val = simpledialog.askstring("File name", "Name for audio file when saved in given directory:")
        self.filename = os.path.join(master.newpath,str(val)+".wav")
        wf = wave.open(self.filename, 'wb')
        wf.setnchannels(channels)
        wf.setsampwidth(p.get_sample_size(sample_format))
        wf.setframerate(fs)
        wf.writeframes(b''.join(frames))
        wf.close()
        self.top.destroy()

class continuous_record(object):
    def __init__(self, master):
        self.filename = None
        self.begin = False
        self.stop = False
        self.max_samp = master.lib_dat.continuous_param()
        self.minimum = master.setvalues[3]
        
        self.top=Toplevel(master) 
        self.top.title("Record continuously")
        self.top.geometry('800x400') 
        
        self.frame1 = Frame(self.top)
        self.frame1.pack(side = "left")
        self.frame_disp = Frame(self.top)
        self.frame_disp.pack(side = "right")
        
        self.frame2 = Frame(self.frame1)
        self.frame2.pack(side = "top")
        self.l1= Label(self.frame2, text="Start recording after how many seconds: ")
        self.l1.pack(side = "top")
        self.e1=Entry(self.frame2)
        self.e1.insert(END, 5.00)
        self.e1.pack(side = "bottom")
        
        self.frame3 = Frame(self.frame1)
        self.frame3.pack(side = "bottom")
        self.l2= Label(self.frame3, text="Maximum record time in seconds:")
        self.l2.pack(side = "top")
        self.e2=Entry(self.frame3)
        self.e2.insert(END, 60.00)
        self.e2.pack(side = "bottom")
        
        self.frame4 = Frame(self.frame1)
        self.frame4.pack(side = "bottom")
        self.b1=Button(self.frame4,text='Record',command=lambda : self.Initialize_record(master,None))
        self.b1.pack()
        self.b2=Button(self.frame4,text='Cancel',command=lambda : (self.stop_cont()))
        self.b2["state"] = "disabled"
        
        self.b = Button(self.top,text='Close window',command=lambda : self.top.destroy())
        self.b.pack(side = "bottom")
    
    def timer(self):
        self.b1["state"] = "disabled"
        self.b["state"] = "disabled"
        self.b2["state"] = "normal"
        try:
            t = float(self.e1.get())
            max_t = float(self.e2.get())
            if t < 0.0:
                t = 5.0
            if max_t <0.0:
                max_t = 60.0
        except:
            messagebox.showwarning(title=None, message="One of the inserted values could not be converted to a float.")
            return 60.0
            
        frequency = 2500  # Set Frequency To 2500 Hertz
        duration = 100  # Set Duration To 100 ms == 0.1 second
        
        while t>0.0: 
            winsound.Beep(frequency, duration)
            time.sleep(0.9)
            t -= 1.0
        return max_t
    
    def stop_cont(self):
        self.stop = True
    
    def Initialize_record(self, master, chunks_left):
        if not self.begin:
            max_t = self.timer()
            self.chunk = 1024  # Record in chunks of 1024 samples
            self.sample_format = pyaudio.paInt16  # 16 bits per sample
            self.channels = 1
            self.fs = master.lib_dat.samp
            self.frames = []  # Initialize array to store frames
            self.length_frames = 0
            self.begin = True
            if self.fs == 0:
                self.fs = 44100  # Record at 44100 samples per second
            self.p = pyaudio.PyAudio()  # Create an interface to PortAudio
            self.stream = self.p.open(format=self.sample_format,
                            channels=self.channels,
                            rate=self.fs,
                            frames_per_buffer=self.chunk,
                            input=True)
            data = self.stream.read(self.chunk)
            self.frames.append(data)
            self.array = np.frombuffer(data, np.int16)
            master.after(1, self.Initialize_record(master,int(self.fs / self.chunk * max_t)))
        
        # Store data in chunks for max_t seconds and compare
        elif not self.stop and chunks_left>0:
            data = self.stream.read(self.chunk)
            self.frames.append(data)
            self.length_frames+=self.chunk
            self.array = np.append(self.array, np.frombuffer(data, np.int16))
            if self.length_frames>self.max_samp:
                nam = master.lib_dat.continuous_compare(self.array,self.length_frames,self.max_samp, self.chunk, self.minimum)
                if nam:
                    self.l = Label(self.frame_disp,text = nam)
                    self.l.pack()
            master.after(1, self.Initialize_record(master,chunks_left-1))
        
        else:
            self.stream.stop_stream()
            self.stream.close()
            self.p.terminate()
            self.begin = False
            self.stop = False
        
            #save as file
            val = simpledialog.askstring("File name", "Name for audio file when saved in given directory:")
            self.filename = os.path.join(master.newpath,str(val)+".wav")
            wf = wave.open(self.filename, 'wb')
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.p.get_sample_size(self.sample_format))
            wf.setframerate(self.fs)
            wf.writeframes(b''.join(self.frames))
            wf.close()
            self.top.destroy()
   
class library(object):
    def __init__(self,master):
        self.top=Toplevel(master) 
        self.top.title("Interferometry: Library mode")
        self.top.geometry('800x400')
        
        self.menu = Frame(self.top)
        self.menu.pack(side = "left")
        self.l=Label(self.top,text="If the library already has data in it the chosen data will be added to it.")
        self.l.pack()
        
        self.frame1 = Frame(self.menu)
        self.frame1.pack(side = "top")
        self.l1=Label(self.frame1,text="\n audiofiles of several types are allowed.")
        self.l1.pack()
        self.b1=Button(self.frame1,text='Upload data files',command=lambda : self.uploaddata(master))
        self.b1.pack()
        
        self.frame3 = Frame(self.menu)
        self.frame3.pack()
        self.l2=Label(self.frame3,text="\n Record data")
        self.l2.pack()
        self.b3=Button(self.frame3,text='Single library node',command=lambda : self.recordsin(master))
        self.b3.pack(side = "right")
        
        self.frame4 = Frame(self.menu)
        self.frame4.pack()
        self.frame4top = Frame(self.frame4)
        self.frame4top.pack()
        self.l3=Label(self.frame4top,text="\n Adjust")
        self.l3.pack()
        self.e1=Entry(self.frame4top)
        self.e1.pack(side = "left")
        self.b4=Button(self.frame4top,text='Remove one library node',command= lambda : self.remove(master))
        self.b4.pack(side = "right")
        self.frame4mid = Frame(self.frame4)
        self.frame4mid.pack()
        self.b5=Button(self.frame4mid,text='Delete all',command=lambda : self.clearup(master))
        self.b5.pack(side = "bottom")
        self.frame4bot = Frame(self.frame4)
        self.frame4bot.pack()
        self.e2=Entry(self.frame4bot)
        self.e2.pack(side = "left")
        self.b6=Button(self.frame4bot,text='Change name of this node',command= lambda : self.node_name(master))
        self.b6.pack(side = "right")
        
        self.frame5 = Frame(self.menu)
        self.frame5.pack()
        self.l4=Label(self.frame5,text="\n\n\n")
        self.l4.pack(side = "top")
        self.b=Button(self.frame5,text='Ok',command= lambda : self.cleanup(master))
        self.b.pack(side = "bottom")
        
        self.display = Frame(self.top)
        self.display.pack(side = "right")
        self.table = Frame(self.display)
        self.table.pack(side = "left")
        self.update_display(master)
         
        self.b4["state"] = "disabled" 
        self.b5["state"] = "disabled" 
        self.b6["state"] = "disabled"
    
    def busy(self):
        self.b["state"] = "disabled"
        self.b1["state"] = "disabled" 
        self.b3["state"] = "disabled" 
        self.b4["state"] = "disabled" 
        self.b5["state"] = "disabled" 
        self.b6["state"] = "disabled" 
           
    def done(self):
        self.b["state"] = "normal"
        self.b1["state"] = "normal"
        self.b3["state"] = "normal"
        self.b4["state"] = "normal"
        self.b5["state"] = "normal"
        self.b6["state"] = "normal"
    
    def update_display(self, master):
        self.table.destroy()
        self.table = Frame(self.display)
        self.table.pack(side = "left")
        if master.lib_dat.length > 0:
            master.lib_dat.filter_lib(master.setvalues[0], master.setvalues[1], master.setvalues[2], master.setvalues[5], master.setvalues[6])
            self.create_table(self.table, master)
            winsound.Beep(10000, 100)
            winsound.Beep(2500, 200)
            
        else:
            self.l5=Label(self.table,text="No library yet")
            self.l5.pack()
              
    def create_table(self, frame, master):
        red = master.setvalues[4]
        for i in range(master.lib_dat.length+1):
            for j in range(master.lib_dat.length+1):
                self.e = Entry(frame, width=10, fg='blue', font=('Arial',16,'bold'))
                self.e.grid(row=i, column=j)
                if i == 0 and j == 0:
                    self.e.insert(END, "Sm \ Sref")
                elif i == 0:
                    self.e.insert(END, master.lib_dat.nodes[j].name)
                elif j == 0:
                    self.e.insert(END, master.lib_dat.nodes[i].name)
                else:
                    cross = master.lib_dat.libar[i-1][j-1]
                    self.e.insert(END, cross)
                    if cross >= red:
                        self.e.config(fg = 'red')
                                              
    def uploaddata(self, master):
        self.busy()
        self.filenames =  filedialog.askopenfilenames(initialdir = "/",title = "Select file",filetypes = [("Audio files", "*.mp3 *.m4a *.wav"),("Data sets", "*.xlsx"),("All Files", "*.*")])
        if self.filenames:
            for i in self.filenames:
                #firstpart, file_extension = os.path.splitext(i)
                #if file_extension == "xlsx":
                    #master.lib_dat.add_lib(i)
                #else:
                    try:
                        master.lib_dat.add_node(i)
                        a,b = self.modify( (master.lib_dat.nodes[master.lib_dat.length].dar), master)
                        master.lib_dat.nodes[master.lib_dat.length].modify(a,b)
                        master.lib_dat.nodes[master.lib_dat.length].after_filter(master.setvalues[0], master.setvalues[1], master.setvalues[2], master.setvalues[5], master.setvalues[6])
                        if master.lib_dat.length == 1:
                            master.lib_dat.lib_array()
                        else:
                            master.lib_dat.update_lib_array()
                        self.update_display(master)
                    except KeyError:
                        None
        self.done()
    
    def modify(self,array, master):
        self.mod_frame=mod_window(master, array)
        master.wait_window(self.mod_frame.top)
        return (self.mod_frame.begin, self.mod_frame.end)
    
    def node_name(self, master):
        self.busy()
        e = self.e2.get()
        if e:
            val, name = master.lib_dat.change_node_name(self.e2.get())
            if val and name:
                self.e = Entry(self.table, width=10, fg='blue', font=('Arial',16,'bold'))
                self.e.grid(row=0, column=val)
                self.e.insert(END, name)
                self.e = Entry(self.table, width=10, fg='blue', font=('Arial',16,'bold'))
                self.e.grid(row=val, column=0)
                self.e.insert(END, name)
            self.done()
        else:
            messagebox.showwarning(title=None, message="Input empty")
            self.done()
        
    def recordsin(self, master):
        self.busy()
        self.record_frame=single_record(master)
        master.wait_window(self.record_frame.top)
        f = self.record_frame.filename
        if f:
            master.lib_dat.add_node(f)
            a,b = self.modify((master.lib_dat.nodes[master.lib_dat.length].dar), master)
            master.lib_dat.nodes[master.lib_dat.length].modify(a,b)
            if master.lib_dat.length == 1:
                master.lib_dat.lib_array()
            else:
                master.lib_dat.update_lib_array()
            self.update_display(master)
        self.done()
    
    def remove(self, master):
        self.busy()
        master.lib_dat.remove_node(self.e1.get())
        self.update_display(master)
        self.done()
        if master.lib_dat.length ==0:
            self.b4["state"] = "disabled" 
            self.b5["state"] = "disabled" 
            self.b6["state"] = "disabled"
             
    def clearup(self, master):
        self.busy()
        master.lib_dat.remove_library()
        self.update_display(master)
        self.done()
        self.b4["state"] = "disabled" 
        self.b5["state"] = "disabled" 
        self.b6["state"] = "disabled"
    
    def save_lib(self, master, filename):
        self.busy()
        workbook = xlsxwriter.Workbook(filename)
        worksheet1 = workbook.add_worksheet("library")
        
        worksheet1.write(0, 0, 'Amount of library nodes')
        worksheet1.write(1, 0, master.lib_dat.length)
        worksheet1.write(0, 1, 'Sampling frequency used')
        worksheet1.write(1, 1, master.lib_dat.samp)
        
        types = ["Without filtering:", "Low pass Filter:", "High pass Filter", "Band pass filter"]
        l = master.lib_dat.length
        f_1 = master.setvalues[1]
        f_2 = master.setvalues[2]
        f_3 = master.setvalues[5]
        f_4 = master.setvalues[6]
        
        if f_1 == f_2 == f_3 == f_4 == 0:
            f_1, f_2 = master.lib_dat.frequency_bounds()
        
        f_1 = max(f_1, 0)
        
        worksheet1.write(0, 2, 'f_1')
        worksheet1.write(1, 2, f_1)
        worksheet1.write(0, 3, 'f_2')
        worksheet1.write(1, 3, f_2)
        worksheet1.write(0, 4, 'f_3')
        worksheet1.write(1, 4, f_1)
        worksheet1.write(0, 5, 'f_4')
        worksheet1.write(1, 5, f_2)
        
        for f in range(4):
            worksheet1.write(3, f*(l+2), types[f])
            master.lib_dat.filter_lib(f,f_1,f_2, f_3, f_4)
            for i in range(l+1):
                for j in range(l+1):
                    if i == 0 and j == 0:
                        worksheet1.write(4+i, f*(l+2)+j, "Sm \ Sref")
                    elif i == 0:
                        worksheet1.write(4+i, f*(l+2)+j, master.lib_dat.nodes[j].name)
                    elif j == 0:
                        worksheet1.write(4+i, f*(l+2)+j, master.lib_dat.nodes[i].name)
                    else:
                        worksheet1.write(4+i, f*(l+2)+j, master.lib_dat.libar[i-1][j-1])
        
        worksheet2 = workbook.add_worksheet("raw_data")
        for i in range (l):
            worksheet2.write(0, i,  master.lib_dat.nodes[i+1].name)
            n = 1
            for elem in master.lib_dat.nodes[
                    ++i+1].dar:
                worksheet2.write(n, i,  elem)
                n+=1
        
        workbook.close()
        
        plt.figure(figsize = (12,8))
        plt.plot(np.fft.rfft(master.lib_dat.nodes[1].dar))
        plt.xlabel("$f (Hz)$", fontsize = 15)
        plt.ylabel("$F(f) (magnitude)$", fontsize = 15)
        plt.grid()
        plt.savefig(os.path.join(master.newpath, "FFT.png"))
        
        plt.figure(figsize = (12,8))
        plt.plot(np.arange(0.0, float(master.lib_dat.nodes[1].dar.size),1.0)* master.lib_dat.delta(), master.lib_dat.nodes[1].dar)
        plt.xlabel("$time (s)$", fontsize = 15)
        plt.ylabel("$Amplitude$", fontsize = 15)
        plt.grid()
        plt.savefig(os.path.join(master.newpath, "Audio_node.png"))
    
    def cleanup(self, master):
        if master.lib_dat.length> 0:
            val = simpledialog.askstring("File name", "Name for excel file where library is saved:")
            filename = os.path.join(master.newpath,str(val) + ".xlsx")
            self.save_lib(master, filename)
        self.top.destroy()
        
class execution(object):
    def __init__(self,master):
        #intialize several things so execution can be stored
        val = simpledialog.askstring("File name", "Name for excel file where library is saved:")
        self.filename = os.path.join(master.newpath,str(val))
        self.exname = []
        self.exdat = np.array([])
        
        self.top=Toplevel(master) 
        self.top.title("Interferometry: Execution mode")
        self.top.geometry('800x400')
        
        self.menu = Frame(self.top)
        self.menu.pack(side = "left")
        
        self.frame1 = Frame(self.menu)
        self.frame1.pack(side = "top")
        self.l1=Label(self.frame1,text="Several types of audio files are possible. Multiple at the same time as well.")
        self.l1.pack()
        self.b1=Button(self.frame1,text='Upload audiofiles',command=lambda : self.uploaddata(master))
        self.b1.pack()
        
        self.frame2 = Frame(self.menu)
        self.frame2.pack()
        self.l2=Label(self.frame2,text="\n Record data")
        self.l2.pack()
        self.b2=Button(self.frame2,text='Single data node',command=lambda : self.recordsin(master))
        self.b2.pack(side = "right")
        self.b3=Button(self.frame2,text='Continuous stream',command=lambda : self.recordcon(master))
        self.b3.pack(side = "right")
        
        self.frame5 = Frame(self.menu)
        self.frame5.pack()
        self.l4=Label(self.frame5,text="\n\n\n")
        self.l4.pack(side = "top")
        self.b=Button(self.frame5,text='Ok',command=lambda : self.cleanup(master))
        self.b.pack(side = "bottom")
        
        self.display = Frame(self.top)
        self.display.pack(side = "right")
        self.table = Frame(self.display)
        self.table.pack(side = "left")
        self.l5=Label(self.table,text="No data points yet")
        self.l5.pack()
    
    def busy(self):
        self.b["state"] = "disabled"
        self.b1["state"] = "disabled" 
        self.b2["state"] = "disabled"  
        self.b3["state"] = "disabled"
              
    def done(self):
        self.b["state"] = "normal"
        self.b1["state"] = "normal"
        self.b2["state"] = "normal"
        self.b3["state"] = "normal"
    
    def empty_display(self, master):
        self.table.destroy()
        self.table = Frame(self.display)
        self.table.pack(side = "left")
        self.tabletitle = Frame(self.table)
        self.tabletitle.pack(side = "top")
        for i in range(master.lib_dat.length+1):
            self.e = Entry(self.tabletitle, width=20, fg='blue', font=('Arial',16,'bold'))
            self.e.grid(row=0, column=i)
            if i == 0:
                self.e.insert(END, "Sm \ Sref")
            else:
                self.e.insert(END, master.lib_dat.nodes[i].name)
        
    def add_to_table(self, frame, master):
        green = master.setvalues[3]
        l = len(self.exname)
        for i in range(master.lib_dat.length+1):
            self.e = Entry(frame, width=20, fg='blue', font=('Arial',16,'bold'))
            self.e.grid(row=l, column=i)
            if i == 0:
                self.e.insert(END, self.exname[-1])
            else:
                if l == 1:
                    cross = self.exdat[i-1]
                else:
                    cross = self.exdat[l-1,i-1]
                self.e.insert(END, cross)
                if cross >= green:
                    self.e.config({"background": "Green"})
    
    def uploaddata(self, master):
        self.busy()
        self.filenames =  filedialog.askopenfilenames(initialdir = "/",title = "Select file",filetypes = [("Audio files", "*.mp3 *.m4a *.wav"),("All Files", "*.*")])
        if self.filenames:
            self.empty_display(master)
            for i in self.filenames:
                #try:
                    name = str(simpledialog.askstring("Name for data node", "What data node:" + str(i)))
                    samp = master.lib_dat.samp
                    execution_node = data_node(name, samp)
                    execution_node.file(i)
                    a,b = self.modify(execution_node.dar, master)
                    execution_node.modify(a,b)
                    execution_node.after_filter(master.setvalues[0], master.setvalues[1], master.setvalues[2], master.setvalues[5], master.setvalues[6])
                    self.exname.append(name)
                    self.update_exdat(master, execution_node)
                #except:
                    #messagebox.showwarning(title = None, message = "Error: file not found or other I/O error. (DECODING FAILED)")        
        self.done()
    
    def update_exdat(self, master, execution_node):
        ar = master.lib_dat.compare_to_library(execution_node)
        if self.exdat.size < 1:
            self.exdat = ar
        else:
            self.exdat = np.append(self.exdat, ar, axis=0)
        frame = Frame(self.table)
        frame.pack()
        self.add_to_table(frame, master)
           
    def modify(self,array, master):
        self.mod_frame=mod_window(master, array)
        master.wait_window(self.mod_frame.top)
        return self.mod_frame.begin, self.mod_frame.end
  
    def recordcon(self, master):
        self.busy()
        self.continuous_record_frame=continuous_record(master)
        master.wait_window(self.continuous_record_frame.top)
        self.done()
        
    def recordsin(self, master):
        self.busy()
        self.record_frame=single_record(master)
        master.wait_window(self.record_frame.top)
        f = self.record_frame.filename
        if f:
            name = str(simpledialog.askstring("Name for data node in excel", "What data node:"))
            samp = master.lib_dat.samp
            execution_node = data_node(name, samp)
            execution_node.file(f)
            a,b = self.modify(execution_node.dar, master)
            execution_node.modify(a,b)
            execution_node.after_filter(master.setvalues[0], master.setvalues[1], master.setvalues[2], master.setvalues[5], master.setvalues[6])
            self.exname.append(name)
            self.update_exdat(master, execution_node)
        self.done()
    
    def save_ex(self, master, filename):
        self.busy()
        workbook = xlsxwriter.Workbook(filename)
        worksheet1 = workbook.add_worksheet("execution_table")
        worksheet1.write(0, 0, 'S_m\S_ref')
        l = master.lib_dat.length
        h = len(self.exname)
        for i in range (l):
            worksheet1.write(0, i+1,  master.lib_dat.nodes[i+1].name)
        for j in range (h):
            worksheet1.write(1+j, 0, self.exname[j])
        for k in range(h):
            for m in range(l):
                 worksheet1.write(k+1, m+1, self.exdat[k,m])
        workbook.close()
    
    def cleanup(self, master):
        if master.lib_dat.length>0 and len(self.exname)>0:
            val = simpledialog.askstring("File name", "Name for excel file where library is saved:")
            filename = os.path.join(master.newpath,str(val)+".xlsx")
            self.save_ex(master, filename)
        self.top.destroy()
        
class settings(object):
    def __init__(self,master):
        self.top=Toplevel(master) 
        self.top.title("Interferometry: Settings")
        self.top.geometry('600x600')
        
        self.frame1 = Frame(self.top)
        self.frame1.pack(side = "top")
        self.l1=Label(self.frame1,text="What filter:")
        self.l1.pack()
        self.v0= master.setvalues[0]
        self.r0=Radiobutton(self.frame1, text="No filter", variable=self.v0,value=1)
        self.r0.pack()
        self.r1=Radiobutton(self.frame1, text="Low pas filter", variable=self.v0,value=2)
        self.r1.pack()
        self.r2=Radiobutton(self.frame1, text="High pas filter", variable=self.v0,value=3)
        self.r2.pack()
        self.r3=Radiobutton(self.frame1, text="Band width filter", variable=self.v0,value=4)
        self.r3.pack()
        
        self.frame2 = Frame(self.top)
        self.frame2.pack()
        
        self.frame2left = Frame(self.top)
        self.frame2left.pack(side = "left")
        self.l2=Label(self.frame2left,text="\n Frequency bounds high-pass:")
        self.l2.pack()
        self.frame2lefttop = Frame(self.frame2left)
        self.frame2lefttop.pack(side = "top")
        self.l3=Label(self.frame2lefttop,text="Lowest:")
        self.l3.pack(side = "left")
        self.e1=Entry(self.frame2lefttop)
        self.e1.insert(END, master.setvalues[1])
        self.e1.pack(side = "right")
        self.frame2leftbot = Frame(self.frame2left)
        self.frame2leftbot.pack(side = "bottom")
        self.l4=Label(self.frame2leftbot,text="Highest:")
        self.l4.pack(side = "left")
        self.e2=Entry(self.frame2leftbot)
        self.e2.insert(END, master.setvalues[2])
        self.e2.pack(side = "right")
        
        self.frame2right = Frame(self.top)
        self.frame2right.pack(side = "right")
        self.l7=Label(self.frame2right,text="\n Frequency bounds low-pass:")
        self.l7.pack()
        self.frame2righttop = Frame(self.frame2right)
        self.frame2righttop.pack(side = "top")
        self.l8=Label(self.frame2righttop,text="Lowest:")
        self.l8.pack(side = "left")
        self.e5=Entry(self.frame2righttop)
        self.e5.insert(END, master.setvalues[5])
        self.e5.pack(side = "right")
        self.frame2rightbot = Frame(self.frame2right)
        self.frame2rightbot.pack(side = "bottom")
        self.l9=Label(self.frame2rightbot,text="Highest:")
        self.l9.pack(side = "left")
        self.e6=Entry(self.frame2rightbot)
        self.e6.insert(END, master.setvalues[6])
        self.e6.pack(side = "right")
        
        self.frame3 = Frame(self.top)
        self.frame3.pack()
        self.l5=Label(self.frame3,text="\n Approve execution values higher than")
        self.l5.pack()
        self.e3=Entry(self.frame3)
        self.e3.insert(END, master.setvalues[3])
        self.e3.pack()
        
        self.frame4 = Frame(self.top)
        self.frame4.pack()
        self.l6=Label(self.frame4,text="\n Give warning at library for different nodes with values over")
        self.l6.pack()
        self.e4=Entry(self.frame4)
        self.e4.insert(END, master.setvalues[4])
        self.e4.pack()
        
        self.frame9 = Frame(self.top)
        self.frame9.pack()
        self.l9=Label(self.frame4,text="\n Get graphs from following files")
        self.l9.pack()
        self.b9=Button(self.top,text='Upload data files',command=lambda :self.uploaddata(master))
        self.b9.pack()
        
        self.b=Button(self.top,text='Ok',command=lambda :self.cleanup(master))
        self.b.pack(side = "bottom")
    
    def modify(self,array, master):
        self.mod_frame=mod_window(master, array)
        master.wait_window(self.mod_frame.top)
        return (self.mod_frame.begin, self.mod_frame.end)
    
    def uploaddata(self, master):
        self.filenames =  filedialog.askopenfilenames(initialdir = "/",title = "Select file",filetypes = [("Audio files", "*.mp3 *.m4a *.wav"),("All Files", "*.*")])
        if self.filenames:
            for i in self.filenames:
                try:
                    name = str(simpledialog.askstring("Name for data node", "What data node:" + str(i)))
                    node = data_node(name, 0.0)
                    node.file(i)
                    a,b = self.modify(node.dar, master)
                    node.modify(a,b)
                    
                    FFT = np.fft.rfft(node.dar)
                    
                    plt.figure(figsize = (12,8))
                    plt.plot(FFT)
                    plt.xlabel("$f (Hz)$", fontsize = 15)
                    plt.ylabel("$F(f) (magnitude)$", fontsize = 15)
                    plt.grid()
                    plt.savefig(os.path.join(master.newpath, name + "_FFT.png"))
    
    
                    plt.figure(figsize = (12,8))
                    plt.plot(np.arange(0.0, float(node.dar.size),1.0)/node.samp, node.dar)
                    x = (float(node.dar.size)/node.samp)//0.1
                    plt.xticks(np.arange(0.0, x*0.1 + 0.1, 0.1))
                    plt.xlabel("$time (s)$", fontsize = 15)
                    plt.ylabel("$Amplitude$", fontsize = 15)
                    plt.grid()
                    plt.savefig(os.path.join(master.newpath, name + "_Audio_node.png"))
                    
                    abs_FFT = np.absolute(FFT)
                    plt.figure(figsize = (12,8))
                    plt.plot(abs_FFT)
                    plt.xlabel("$f (Hz)$", fontsize = 15)
                    plt.ylabel("$|F(f)| (magnitude)$", fontsize = 15)
                    plt.grid()
                    plt.savefig(os.path.join(master.newpath, name + "_real_FFT.png"))
                    
                    val1 = float(self.e1.get())
                    val2 = float(self.e2.get())
                    val3 = float(self.e5.get())
                    val4 = float(self.e6.get())
                    
                    if not val1 == val2 == val3 == val4 == 0.0:
                        abs_FFT = np.absolute(FFT)
                        plt.figure(figsize = (12,8))
                        plt.plot(abs_FFT)
                        plt.vlines([val1,val2,val3,val4],0,np.max(abs_FFT),colors = 'red',label=['f1','f2','f3','f4'])
                        plt.xlabel("$f (Hz)$", fontsize = 15)
                        plt.ylabel("$|F(f)| (magnitude)$", fontsize = 15)
                        plt.xlim([0,8000])
                        plt.grid()
                        plt.savefig(os.path.join(master.newpath, name + "_real_FFT.png"))
                        
                        node.after_filter(2, val1, val2, val3, val4)    
                        plt.figure(figsize = (12,8))
                        plt.plot(np.arange(0.0, float(node.s.size),1.0)/node.samp, node.s)
                        plt.xlabel("$time (s)$", fontsize = 15)
                        plt.ylabel("$Amplitude$", fontsize = 15)
                        plt.grid()
                        plt.savefig(os.path.join(master.newpath, name + '_' + str(round(val3,1)) + '_' + str(round(val4,1)) + "_low_pass_Audio_node.png"))
                        
                        node.after_filter(3, val1, val2, val3, val4) 
                        plt.figure(figsize = (12,8))
                        plt.plot(np.arange(0.0, float(node.s.size),1.0)/node.samp, node.s)
                        plt.xlabel("$time (s)$", fontsize = 15)
                        plt.ylabel("$Amplitude$", fontsize = 15)
                        plt.grid()
                        plt.savefig(os.path.join(master.newpath, name + '_' + str(round(val1,1)) + '_' + str(round(val2,1)) + "_high_pass_Audio_node.png"))
                        
                        node.after_filter(4, val1, val2, val3, val4) 
                        plt.figure(figsize = (12,8))
                        plt.plot(np.arange(0.0, float(node.s.size),1.0)/node.samp, node.s)
                        plt.xlabel("$time (s)$", fontsize = 15)
                        plt.ylabel("$Amplitude$", fontsize = 15)
                        plt.grid()
                        plt.savefig(os.path.join(master.newpath, name + '_' + str(round(val1,1)) + '_' + str(round(val2,1)) + '_' + str(round(val3,1)) + '_' + str(round(val4,1)) + "_band_pass_Audio_node.png"))   
                except:
                    messagebox.showwarning(title = None, message = "Error: file not found or other I/O error. (DECODING FAILED)")        
    
    def cleanup(self,master):
        try:
            val1 = float(self.e1.get())
            val2 = float(self.e2.get())
            val3 = float(self.e3.get())
            val4 = float(self.e4.get())
            val5 = float(self.e5.get())
            val6 = float(self.e6.get())
            if val1>val2 or val5>val6:
                messagebox.showwarning(title=None, message="The minimum value is higher than the maximum value")
            elif val3>1 or val3<0:
                messagebox.showwarning(title=None, message="'Approve execution values higher than' has a wrong value. Should be between 0 and 1")
            elif val4>1 or val4<0:
                messagebox.showwarning(title=None, message="'Give warning at library for different nodes with values over' has a wrong value. Should be between 0 and 1")
            else:
                master.setvalues = np.array([self.v0,val1,val2,val3,val4,val5,val6])
                self.top.destroy()
        except ValueError:
            messagebox.showwarning(title=None, message="One of the inserted values could not be converted to a float.")

class save(object):
    def __init__(self,master):
        self.dire = ""
        self.name = ""
        
        self.top=Toplevel(master) 
        self.top.geometry('1000x300')
        self.top.overrideredirect(True)
        
        self.frame1 = Frame(self.top)
        self.frame1.pack(side = "top")
        self.l1=Label(self.frame1,text="Save settings: \n")
        self.l1.pack()
        
        self.frame1top = Frame(self.frame1)
        self.frame1top.pack(side = "top")
        self.v0=IntVar()
        self.v0.set(0)
        self.b1=Button(self.frame1top,text='Browse directory',command=self.directory)
        self.b1.pack()
        
        self.frame1mid = Frame(self.frame1)
        self.frame1mid.pack()
        self.l3=Label(self.frame1mid,text="Folder name:")
        self.l3.pack(side = "left")
        self.e1=Entry(self.frame1mid)
        self.e1.pack(side = "right")
        
        self.frame1bot = Frame(self.frame1)
        self.frame1bot.pack()
        self.l4=Label(self.frame1bot,text="This program automatically saves all audio datafiles during execution if they were not uploaded to it. The library is saved whenever library mode is closed.")
        self.l4.pack()
        
        self.l5=Label(self.frame1,text="\n ")
        self.l5.pack()
        self.b=Button(self.frame1,text='Done',command=lambda :self.cleanup(master))
        self.b.pack(side = "bottom")
        
        
    def directory(self):
        self.b["state"] = "disabled"
        self.b1["state"] = "disabled" 
        self.e1["state"] = "disabled" 
        self.dire = filedialog.askdirectory(mustexist = True)
        self.l2=Label(self.frame1top,text=self.dire)
        self.l2.pack()
        self.b["state"] = "normal"
        self.b1["state"] = "normal" 
        self.e1["state"] = "normal" 
        
    
    def cleanup(self,master):
        val1 = self.e1.get()
        if self.dire:
            self.b1.config({"background": "Green"})
            if val1:
                master.newpath = os.path.join(self.dire,str(val1))
                try:
                    if not os.path.exists(master.newpath):
                        os.makedirs(master.newpath)
                    self.top.destroy()
                except:
                    messagebox.showwarning(title = None, message = "Error: path invalid")
            else:
                self.e1.config({"background": "Red"})
        else:
            self.b1.config({"background": "Red"})
            
class main_win(object):
    def __init__(self,master):
        self.master=master
        self.master.title("Interferometry: main")
        self.master.geometry('300x200')
        
        #standard settings
        self.master.setvalues = np.array([1,0.0,0.0,0.7,0.7,0.0,0.0])
        #filter, lowest f high, highest f high, minimum acceptance, minimum for error, lowest f low, highest f low
        
        #initializes the library 
        self.master.lib_dat = library_data()
        
        self.l=Label(self.master,text="Choose your mode:")
        self.l.pack()
        self.top_frame = Frame(master)
        self.top_frame.pack()
        self.bottom_frame = Frame(master)
        self.bottom_frame.pack(side = "bottom")
        
        self.b1=Button(self.top_frame, text = "Library mode", command=self.library)
        self.b1.pack()
        
        self.b2=Button(self.top_frame, text = "Execution mode", command=self.execution)
        self.b2.pack()
        self.b2["state"] = "disabled" 
        
        self.b3=Button(self.bottom_frame, text = "Settings", command=self.settings)
        self.b3.pack(side = "left")
        
        self.b=Button(self.bottom_frame, text = "Exit", command=self.master.destroy)
        self.b.pack(side = "bottom")
        
        self.save()
        
        
        
    def busy(self):
        self.b1["state"] = "disabled" 
        self.b2["state"] = "disabled" 
        self.b3["state"] = "disabled" 
    
    
    def done(self):
        self.b1["state"] = "normal"
        self.b2["state"] = "normal"
        self.b3["state"] = "normal"
        
    def library(self):
        self.busy()
        self.w=library(self.master)
        self.master.wait_window(self.w.top)
        self.done()
        if self.master.lib_dat.length == 0:
            self.b2["state"] = "disabled"
        
    
    def execution(self):
        self.busy()
        self.w=execution(self.master)
        self.master.wait_window(self.w.top)
        self.done()
        
    def settings(self):
        self.busy()
        self.w=settings(self.master)
        self.master.wait_window(self.w.top)
        self.done()
        if self.master.lib_dat.length == 0:
            self.b2["state"] = "disabled"
    
    def save(self):
        self.busy()
        self.w=save(self.master)
        self.master.wait_window(self.w.top)
        self.done()
        self.b2["state"] = "disabled"
          

if __name__ == "__main__":
    win=Tk()
    m=main_win(win)
    win.mainloop()

