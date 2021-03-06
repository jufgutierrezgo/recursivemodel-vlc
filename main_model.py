"""
RECURSIVE MODEL CHANNEL FOR VISIBLE LIGHT COMMUNICATION
Juan Felipe Gutierrez
jufgutierrezgo@unal.edu.co

This software includes the following improvements:
- Using of the fast euclidean distance function
- Add a new dimension to the array_points, a wall label
- The array_parameter is computed only with half matrix 
- Was created a general reports about channel impulse reponse.
- Was modified the equation reflection using 4 angles instead of 3 angles

"""
import numpy as np
import numpy
import math
import os

# annotating a variable with a type-hint
from typing import List, Tuple

import matplotlib.pyplot as plt
import mpl_toolkits.mplot3d.axes3d as axes3d

import fractions
from fractions import Fraction

from fastdist import fastdist

import timeit

from numpy.core.function_base import linspace

from scipy.fft import rfft, rfftfreq

# global variables

#speed of light in [m/s]
SPEED_OF_LIGHT = 3e8 
# time resolution for histogram
TIME_RESOLUTION = 0.2e-9 
# bins for power graph histogram
BINS_HIST = 300 
#Array with normal vectors for each wall.
NORMAL_VECTOR_WALL = [[0,0,-1],[0,1,0],[1,0,0],[0,-1,0],[-1,0,0],[0,0,1]]
#directory root of the project
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
#directory to save channel impulse response raw data
CIR_PATH = ROOT_DIR + "/cir/"
#directory to save histograms and graphs  
REPORT_PATH = ROOT_DIR + "/report/"


#Function to calculate angls between two vector position
def cos_2points(
    v1: List[float],
    n1: List[int],
    v2: List[float],
    n2: List[int]
    ) -> Tuple[float,float]:

    unit_vlos = (v1-v2) / np.linalg.norm(v1-v2)

    cos_phi = np.dot(-1*unit_vlos, n1)
    cos_tetha = np.dot(unit_vlos, n2)   
    
    #print([angle1,angle2])    
    return cos_phi,cos_tetha



def led_pattern(m: float) -> None:
    """Function to create a 3d radiation pattern of the LED source.
    
    The LED for recurse channel model is assumed as lambertian radiator. The number of lambert 
    defines the directivity of the light source.
        
    Parameters:
        m: Lambert number
    
    Returns: None.
        
    """

    theta, phi = np.linspace(0, 2 * np.pi, 40), np.linspace(0,np.pi/2, 40)
    THETA, PHI = np.meshgrid(theta, phi)
    R = (m+1)/(2*np.pi)*np.cos(PHI)**m
    X = R * np.sin(PHI) * np.cos(THETA)
    Y = R * np.sin(PHI) * np.sin(THETA)
    Z = R * np.cos(PHI)
    fig = plt.figure()
    ax = fig.add_subplot(1,1,1, projection='3d')
    plot = ax.plot_surface(
        X, Y, Z, rstride=1, cstride=1, cmap=plt.get_cmap('jet'),
        linewidth=0, antialiased=False, alpha=0.5)

    plt.show()
    return 0


def tessellation(
    x_lim: float,
    y_lim: float,
    z_lim: float,
    scale_factor:float
    ) -> Tuple[List[float], int, int, int, int, float, int]:
    """Function to calculate the coordinates [x,y,z] of every points.
    
    It assumes a rectangular room and each of ones of walls are splitted in small 
    square cells. The centroid of each small cell represents a point coordinates 
    that will be returned. Is also returned the number of points and the number of 
    division in each axe. Using a scale factor is possible modify the number of 
    cells used in the model.

    Paramteres:
        x_lim: lenght of rectangular room in x-axe
        y_lim: lenght of rectangular room in y-axe
        z_lim: lenght of rectangular room in z-axe 
        scale_factor: scale factor

    Returns: A tuple with the follow parameters:
        array_points = 2d-array (3xNc) with [X,Y,Z] coordinates of each points.
        no_xtick,no_ytick,no_ztick: Number of divisions in each axe.
        init_index: 1d-array with start index for each wall inside of array_points.
        delta_A: cell area in the model
        no_points: number of points (or cells) in the model 
    
    """


    print("//****** Tessellation *******//")
    x_num = fractions.Fraction(str(x_lim)).numerator
    x_den = fractions.Fraction(str(x_lim)).denominator
    y_num = fractions.Fraction(str(y_lim)).numerator
    y_den = fractions.Fraction(str(y_lim)).denominator    
    z_num = fractions.Fraction(str(z_lim)).numerator
    z_den = fractions.Fraction(str(z_lim)).denominator    

    #print(x_num,x_den,y_num,y_den,z_num,z_den)
    den_lcm = lcm(x_den,y_den,z_den)
        
    n_x = int(den_lcm*x_num/x_den)
    n_y = int(den_lcm*y_num/y_den)
    n_z = int(den_lcm*z_num/z_den)
    #print(n_x,n_y,n_z)
    #print(den_lcm)

    num_gfc = math.gcd(n_z,math.gcd(n_x,n_y))
    #print(num_gfc)

    delta_Lmax = num_gfc / den_lcm 
    print("DeltaL max is: ", delta_Lmax)
    delta_Amax = delta_Lmax**2
    print("DeltaA max is: ", delta_Amax)
    
    #Scaling factor for delta_Lmax (1/2,1/3,1/4....)
    delta_L = delta_Lmax*scale_factor

    #DeltaA is defined from root(2)*DeltaL/2, because is the minimum distance between two points
    #delta_A = (delta_L/20)**2
    
    #DeltaA is defined from time-clearesolution presented in main reference.
    #delta_A = 3.6e-3
    
    #DeltaA defined to fulfill deltaA << (root(2)/2)*deltaL --> the maximun lenght on delta_A must be 10 times less than distane between points 
    delta_A = (delta_L**2)/200

    print("Scale factor for Delta L is: ", scale_factor)
    print("DeltaL[m]: ", delta_L)
    print("DeltaA[m^2]: ", delta_A)


    no_xtick = int(x_lim/delta_L)
    no_ytick = int(y_lim/delta_L)
    no_ztick = int(z_lim/delta_L)

    ew0_points = np.zeros((4,no_xtick*no_ytick))
    ew1_points = np.zeros((4,no_ztick*no_xtick))
    ew2_points = np.zeros((4,no_ztick*no_ytick))
    ew3_points = np.zeros((4,no_ztick*no_xtick))
    ew4_points = np.zeros((4,no_ztick*no_ytick))
    ew5_points = np.zeros((4,no_xtick*no_ytick))

    #Init_index define the index where each point in parameters start, eg. ew_0 start in index 0, and ew_1 in no_xtick*no_ytick index
    init_index = np.zeros(6)
    points = [ew0_points,ew1_points,ew2_points,ew3_points,ew4_points,ew5_points]

    

    for i in range(1,6):
        init_index[i] = int(len(points[i-1][0,:]) + init_index[i-1])
    
    counter_cell = 0

    for j in range(0,no_xtick):
        for i in range(0,no_ytick):
            ew0_points[0,counter_cell] = delta_L/2 + j*delta_L
            ew0_points[1,counter_cell] = delta_L/2 + i*delta_L         
            ew0_points[2,counter_cell] = z_lim
            ew0_points[3,counter_cell] = 0         

            ew5_points[0,counter_cell] = delta_L/2 + j*delta_L
            ew5_points[1,counter_cell] = delta_L/2 + i*delta_L         
            ew5_points[2,counter_cell] = 0
            ew5_points[3,counter_cell] = 5         
            counter_cell += 1

    counter_cell = 0

    for j in range(0,no_ztick):
        for i in range(0,no_xtick):
            ew1_points[0,counter_cell] = x_lim - delta_L/2 - i*delta_L
            ew1_points[1,counter_cell] = 0
            ew1_points[2,counter_cell] = z_lim - delta_L/2 - j*delta_L
            ew1_points[3,counter_cell] = 1        
            
            ew3_points[0,counter_cell] = x_lim - delta_L/2 - i*delta_L
            ew3_points[1,counter_cell] = y_lim
            ew3_points[2,counter_cell] = z_lim - delta_L/2 - j*delta_L
            ew3_points[3,counter_cell] = 3         
            counter_cell += 1

    
    counter_cell = 0

    for j in range(0,no_ztick):
        for i in range(0,no_ytick):
            ew2_points[0,counter_cell] = 0
            ew2_points[1,counter_cell] = delta_L/2 + i*delta_L/2
            ew2_points[2,counter_cell] = z_lim - delta_L/2 - j*delta_L
            ew2_points[3,counter_cell] = 2        
            
            ew4_points[0,counter_cell] = x_lim
            ew4_points[1,counter_cell] = delta_L/2 + i*delta_L/2
            ew4_points[2,counter_cell] = z_lim - delta_L/2 - j*delta_L
            ew4_points[3,counter_cell] = 4        
            counter_cell += 1

    no_points=2*no_xtick*no_ytick + 2*no_ztick*no_xtick + 2*no_ztick*no_ytick
    print("The total number of points is: ",no_points)
    print("//-------- points array created --------------//")
    #print(ew0_points)
    #print(ew5_points)
    return [np.concatenate((ew0_points,ew1_points,ew2_points,ew3_points,ew4_points,ew5_points),axis=1),no_xtick,no_ytick,no_ztick,init_index,delta_A,no_points]

#MCM
def lcm(num1: float, num2: float,num3: float) -> float: 
    return abs(num1*num2*num3) // math.gcd(num3,math.gcd(num1, num2))


def make_parameters(
    array_points: List[float],
    x_lim: float,
    y_lim: float,
    z_lim: float,
    no_xtick: int,
    no_ytick: int,
    no_ztick: int
    )-> List[float]:

    """This function creates an 3d-array with cross-parametes between points. 
    
    This parameters are the distance between points and the cosine of the angles 
    respect to the normal vector. Using this array is commputed the channel immpulse 
    response.
    
    Parameters:
        array_points: 2d-array with [x,y,z] coordinates for each point. 
        x_lim: lenght of rectangular room in x-axe
        y_lim: lenght of rectangular room in y-axe
        z_lim: lenght of rectangular room in z-axe 
        no_xtick: number of division in x-axe 
        no_ytick: number of division in y-axe 
        no_ztick: number of division in z-axe 

    Returns: Returns a 3d-array with distance and cos(tetha) parameters. The 
    shape of this array is [2,no_points,no_points].
    
    
        _____________________    
       /                    /|
      /                    / |
     /                    /  |
    /____________________/  /| 
    |     Distance       | / |
    |____________________|/ /
    |     Cos(tetha)     | /
    |____________________|/
    

    """
    no_points = 2*no_xtick*no_ytick + 2*no_ztick*no_xtick + 2*no_ztick*no_ytick
    ew_par = np.zeros((2,no_points,no_points),dtype=np.float16)    

    counter_points = 0

    for ini_point in range(0,no_points):        

        for end_point in range(ini_point+1,no_points):
                               
            if array_points[3,ini_point]==array_points[3,end_point]:
                ew_par[0,ini_point,end_point] = 0
                ew_par[1,ini_point,end_point] = 0
            else:
                #ew_par[0,ini_point,end_point] = math.dist(array_points[:,ini_point],array_points[:,end_point])
                wallinit = int(array_points[3,ini_point])               
                wallend = int(array_points[3,end_point])

                ew_par[0,ini_point,end_point] = fastdist.euclidean(array_points[0:3,ini_point],array_points[0:3,end_point])                 
                ew_par[0,end_point,ini_point]  = ew_par[0,ini_point,end_point]

                ew_par[1,ini_point,end_point],ew_par[1,end_point,ini_point] = cos_2points(array_points[0:3,ini_point],NORMAL_VECTOR_WALL[wallinit],
                array_points[0:3,end_point],NORMAL_VECTOR_WALL[wallend])
                
   

    print("//------- parameters array created -----------//")
    #print(h_k[i])   
    #numpy.savetxt("ew_par_dis.csv", ew_par[0,:,:], delimiter=",")  
    #numpy.savetxt("ew_par_cos.csv", ew_par[1,:,:], delimiter=",")  

    return ew_par


def compute_cir(
    m: float,
    tx_pos: List[float],
    rx_pos: List[float],
    points: List[float],
    wall_label: List[float],
    parameters: List[float],
    x_lim: float,
    y_lim: float,
    z_lim: float,
    no_xtick: float,
    no_ytick: float,
    no_ztick: float,
    init_index: float,
    a_r: float,
    rho: float,
    delta_A: float,
    k_reflec: float
    ) -> List[float]:    
    """ Function to compute the channel impulse response for each reflection. 
    
    Parameters:
        m: lambertian number to tx emission
        tx_pos: 1d-array with [x,y,z] tx position
        rx_pos: 1d-array with [x,y,z] rx position
        points: List with [x,y,z] cooridinates for every point in each wall
        parameters: List with angle and distance between all points.  
        x_lim,y_lim,z_lim: limits in room dimmensions
        a_r: sensitive area in photodetector
        no_xtick,no_ytick,no_ztick: number of division in each axes.

    Returns: A list with 2d-array [power_ray,time_delay] collection for each 
    refletion [h_0,h_1,...,h_k].


    """

    
    #compute the total number of points (cells)
    no_cells = len(points[0,:])

    #area factor
    area_factor = (2*x_lim*y_lim + 2*x_lim*z_lim + 2*y_lim*z_lim)/(delta_A*no_cells)

    #define the wall of the tx_pos
    tx_wall = wall_label[tx_pos]
    

    #define the wall of the rx_pos
    rx_wall = wall_label[rx_pos]
    

    for i in range(0,no_cells):
        #print(np.transpose(tx_pos)-points[tx_wall][:,i])        
        if np.allclose(np.transpose(tx_pos),points[:,i]):
            tx_index_point = i
            #print(i)
            break
            

    for i in range(0,no_cells):        
        if np.allclose(np.transpose(rx_pos),points[:,i]):
            rx_index_point = i
            #print(i)
            break

    
    cos_phi = np.zeros((no_cells),dtype=np.float16)
    dis2 = np.zeros((no_cells,no_cells),dtype=np.float16)

    dis2 = np.power(parameters[0,:,:],2)
    
    cos_phi = parameters[1,int(tx_index_point),:]
    tx_power = (m+1)/(2*np.pi)*np.multiply(np.divide(1,dis2[tx_index_point,:],out=np.zeros((no_cells)), where=dis2[tx_index_point,:]!=0),np.power(cos_phi,m))
    rx_wall_factor = a_r*parameters[1,int(rx_index_point),:]

    h0_se = np.zeros((no_cells,2),dtype=np.float32)
    h0_er = np.zeros((no_cells,2),dtype=np.float32)

    
    #Impulse response between source and each cells 
    h0_se[:,0] = np.multiply(area_factor*rho*delta_A*tx_power,parameters[1,:,int(tx_index_point)])
    #Impulse response between receiver and each cells 
    h0_er[:,0] = np.divide(np.multiply(parameters[1,:,int(rx_index_point)],rx_wall_factor),np.pi*dis2[rx_index_point,:],out=np.zeros((no_cells)), where=dis2[rx_index_point,:]!=0)
    #Time delay between source and each cells 
    h0_se[:,1] = parameters[0,tx_index_point,:]/SPEED_OF_LIGHT
    #Time delay between receiver and each cells 
    h0_er[:,1] = parameters[0,rx_index_point,:]/SPEED_OF_LIGHT


    dP_ij = np.zeros((no_cells,no_cells),np.float32)
    dP_ij = np.divide(rho*delta_A*parameters[1,:,:]*np.transpose(parameters[1,:,:]),np.pi*dis2,out=np.zeros_like(dP_ij),where=dis2!=0) 
    #dP_ij_1d = dP_ij.flatten()
    #numpy.savetxt("dPij.csv", dP_ij[:,0], delimiter=",")
    

    h_k = []
    hlast_er = []
    

    for i in range(k_reflec+1):
        h_k.append(np.zeros((int(no_cells**i),2),np.float32))
        hlast_er.append(np.zeros((int(no_cells**i),2),np.float32)) 

        if i == 0:           

            h_k[i][0,0] = tx_power[int(rx_index_point)]*rx_wall_factor[int(tx_index_point)]
            h_k[i][0,1] = parameters[0,int(tx_index_point),int(rx_index_point)]/SPEED_OF_LIGHT

            print("//------------- h0-computed ------------------//")            
            numpy.savetxt(CIR_PATH+"h0.csv", h_k[i], delimiter=",")

        elif i==1:
            hlast_er[i][:,0] = h0_er[:,0]     
            hlast_er[i][:,1] = h0_er[:,1]

            h_k[i][:,0] = np.multiply(h0_se[:,0],h0_er[:,0]) 
            h_k[i][:,1] = h0_se[:,1] + h0_er[:,1]

            print("//------------- h1-computed ------------------//")
            numpy.savetxt(CIR_PATH+"h1.csv", h_k[i], delimiter=",")
            

        else:
            count_blocks = 0
            #print(len(hlast_er[i-1][:,0]))
            #print(len(hlast_er[i][:,0]))
            for j in range(len(hlast_er[i-1][:,0])):

                index_dpij = int(j%no_cells)
                
                hlast_er[i][no_cells*j:int(no_cells*(j+1)),0] = hlast_er[i-1][j,0]*dP_ij[index_dpij,:]
                hlast_er[i][no_cells*j:int(no_cells*(j+1)),1] = hlast_er[i-1][j,1] + parameters[0,index_dpij,:]/SPEED_OF_LIGHT                

            len_last = len(hlast_er[i][:,0])

            for l in range(no_cells):
                
                lim_0 = int(l*(no_cells**(i-1)))
                lim_1 = int((l+1)*(no_cells**(i-1)))
                
                #h_k[i][lim_0:lim_1,0] = h0_se[l,0]*[hlast_er[i][m,0] for m in range(l,len_last,no_cells)]
                #h_k[i][lim_0:lim_1,1] = h0_se[l,1] + [hlast_er[i][m,1] for m in range(l,len_last,no_cells)]

                #h_k[i][lim_0:lim_1,0] = h0_se[l,0]*hlast_er[i][lim_0:lim_1,0] 
                #h_k[i][lim_0:lim_1,1] = h0_se[l,1] + hlast_er[i][lim_0:lim_1,1]
                #print(h0_se[l,0])
                #print([hlast_er[i][m,0] for m in range(l,len_last,no_cells)])
                h_k[i][lim_0:lim_1,0] = np.multiply([hlast_er[i][m,0] for m in range(l,len_last,no_cells)],h0_se[l,0])
                h_k[i][lim_0:lim_1,1] = h0_se[l,1] + [hlast_er[i][m,1] for m in range(l,len_last,no_cells)]

            print("//------------- h"+str(i)+"-computed ------------------//")      
                 
    return h_k

#
def create_histograms(
    h_k: List[float],
    k_reflec: int,
    no_cells: int
    ) -> Tuple[List[float],List[float],List[float]]:
    """Function to create histograms from channel impulse response raw data. 
    
    The channel impulse response raw data is a list with power and time delay 
    of each ray. The histogram are created based on time resolution. 

    Parameters:
        h_k: list with channel impulse response [h_0,h_1,...,h_k]. 
        k_reflec: number of reflections
        no_cells: number of points of model

    Returns: A List with the next parameters
        hist_power_time: Power histograms for each reflection
        total_ht: total power CIR histrogram 
        time_scale: 1d-array with time scale

    """
        
    print("//------------- Data report ------------------//")
    print("Time resolution [s]:"+str(TIME_RESOLUTION))
    print("Number of Bins:"+str(BINS_HIST))
    h_power = np.zeros((k_reflec+1))

    hk_aux = []
    
    delay_los = h_k[0][0,1]
    hist_power_time = np.zeros((BINS_HIST,k_reflec+1))
    


    for i in range(k_reflec+1):            
        
        hk_aux.append(np.zeros((int(no_cells**i),2)))

        # Compute and print the total power per order reflection
        print("h"+str(i)+"-Response:")                       
        h_power[i] = np.sum(h_k[i][:,0])
        print("Power[w]:",h_power[i])
        if i==0:
            print("Delay[s]:",h_k[i][0,1])

        # Create graphs 
               
        hk_aux[i] = h_k[i]
        hk_aux[i][:,1] = hk_aux[i][:,1] - delay_los
        hk_aux[i][:,1] = np.floor(hk_aux[i][:,1]/TIME_RESOLUTION)

        for j in range(no_cells**i):
           hist_power_time[int(hk_aux[i][j,1]),i] += hk_aux[i][j,0]

                
        time_scale = linspace(0,BINS_HIST*TIME_RESOLUTION,num=BINS_HIST)        

    
    print("Total-Response:")
    print("Total-Power[W]:"+str(sum(h_power)))  
    
    total_ht = np.sum(hist_power_time,axis=1)


    return hist_power_time,total_ht,time_scale


def compute_freq(
    hist_power_time: List[float],
    k_reflec: float
    ) -> Tuple[List[float],List[float]]:
    """Function to compute the frequency domain represenation of h(t)
    
    Parameters:
        hist_power_time: power histograms for each reflection
        k_reflec: number of reflections

    Returns:
        hist_power_freq: frequency representation of power histrograms
        xf: frequency scale
    """

    hist_power_freq = np.zeros((int(BINS_HIST/2)+1,k_reflec+1))
    xf = rfftfreq(BINS_HIST, TIME_RESOLUTION)

    for i in range(k_reflec+1):            
        hist_power_freq[:,i] = np.abs(rfft(hist_power_time[:,i]))       

    #plt.plot(xf, np.abs(yf))
    #plt.show()

    return hist_power_freq,xf


def create_hfiles(
    h_k: List[float],
    k_reflec: float
    ) -> None:
    """Function to create .csv of h(t) raw files channel impulse response."""

    for i in range(k_reflec+1):
        numpy.savetxt(CIR_PATH+"h"+str(i)+".csv", h_k[i], delimiter=",") 
    
    return 0

#Function to create .csv files and graphs of power histograms 
def create_histfiles(
    hist_power_time: List[float],
    time_scale: List[float],
    k_reflec: float,
    hfreq: List[float],
    freq: List[float]
    ) -> None:
    """Function to create .csv and graphs of h(t) histogram channel impulse response."""
    
    print("//--- creating-histograms-files-csv-graphs ---//")            

    for i in range(k_reflec+1):
        fig, (vax) = plt.subplots(1, 1, figsize=(12, 6))
        vax.plot(time_scale,hist_power_time[:,i], 'o',markersize=2)
        vax.vlines(time_scale, [0], hist_power_time[:,i],linewidth=1)

        vax.set_xlabel("time(s) \n Time resolution:"+str(TIME_RESOLUTION)+"s  Bins:"+str(BINS_HIST),fontsize=15)
        vax.set_ylabel('Power(W)',fontsize=15)
        vax.set_title("Channel Impulse Response h"+str(i)+"(t)",fontsize=20)

        vax.grid(color = 'black', linestyle = '--', linewidth = 0.5)
        
        numpy.savetxt(REPORT_PATH+"h"+str(i)+"-histogram.csv", np.transpose([hist_power_time[:,i],time_scale.T]), delimiter=",") 

        fig.savefig(REPORT_PATH+"h"+str(i)+".png")        
        plt.show()

    numpy.savetxt(REPORT_PATH+"total-histogram.csv", np.transpose([np.sum(hist_power_time,axis=1),time_scale.T]), delimiter=",") 

    
    for i in range(k_reflec+1):
        fig, (vax) = plt.subplots(1, 1, figsize=(12, 6))
        vax.plot(freq, hfreq[:,i],'o',markersize=2)
        vax.vlines(freq, [0], hfreq[:,i],linewidth=1)

        vax.set_xlabel("Freq(Hz) \n Time resolution:"+str(TIME_RESOLUTION)+"s  Bins:"+str(BINS_HIST),fontsize=15)
        vax.set_ylabel('Power(W)',fontsize=15)
        vax.set_title("Frequency CIR h"+str(i),fontsize=20)

        vax.grid(color = 'black', linestyle = '--', linewidth = 0.5)
        
        numpy.savetxt(REPORT_PATH+"h"+str(i)+"-freq-histogram.csv", [hfreq[:,i],freq], delimiter=",") 

        fig.savefig(REPORT_PATH+"h"+str(i)+"freq.png")        
        plt.show()

    
    print("Graphs and CSV created and saved in directory.")

    return 0


if __name__ == "__main__":
    #define input parameters for channel model
    #source = {tx_pos,txnormal_vector,lambert_num,power[W]}
    #tx_pos: [pos_x,pos_y,pos_z]
    #txnormal_vector: [pos_x,pos_y,pos_z]
    s = [[1,1,2],[0,0,-1],1,1]

    #receiver = {rx_pos,rxnormal_vector,area_receiver[m^2],FOV}
    r = [[1,1,0],[0,0,1],1e-4,1]

    #envirorment e = {reflectance,scale_factor,size_room,k_reflections}
    #size_room: [x_lim,y_lim,z_lim]
    e = [0.8,1/201,[2,2,2],3]    

    starttime = timeit.default_timer()
    #print("The start time is :",starttime)

    array_points,no_xtick,no_ytick,no_ztick,init_index,delta_A,no_points = tessellation(e[2][0],e[2][1],e[2][2],e[1])
    #ew_par = make_parameters(array_points,e[2][0],e[2][1],e[2][2],no_xtick,no_ytick,no_ztick)
    #h_k = compute_cir(s[2],s[0],r[0],array_points[0:3,:],array_points[3,:],ew_par,e[2][0],e[2][1],e[2][2],no_xtick,no_ytick,no_ztick,init_index,r[2],e[0],delta_A,e[3])
    #hist_power_time,total_ht,time_scale = create_histograms(h_k,e[3],no_points)
    #hfreq,freq = compute_freq(hist_power_time,e[3])

    
    #create_hfiles(h_k,e[3])
    #create_histfiles(hist_power_time,time_scale,e[3],hfreq,freq)

    print("The execution time is :", timeit.default_timer() - starttime)
    print("Simulation finished.")

    #print(no_points.shape)
    #print(a[8])

    #led_pattern(s[2])
