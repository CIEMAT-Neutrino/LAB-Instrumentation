import pyvisa
import time
import numpy as np
import matplotlib.pyplot as plt

# Parámetros del barrido
v_start = 0.5            # Voltaje inicial (V)
v_stop = 3              # Voltaje final (V)
v_points = 200              # Número de puntos
v_delay = 0.1               # Tiempo de espera entre puntos (s)
i_limit = 0.01              # Límite de corriente (A)
configured_voltages = np.linspace(v_start, v_stop, v_points)
measures=np.zeros([2,np.shape(configured_voltages)[0]])

# Conectarse al instrumento
rm = pyvisa.ResourceManager()
sm2450 = rm.open_resource('USB0::0x05E6::0x2450::04483997::INSTR')

# Resetear e identificar
sm2450.write("*RST")

# Configurar la fuente
sm2450.write(":SOUR:FUNC VOLT")   # Fuente de voltaje
sm2450.write(":SENS:FUNC 'CURR'") # Medir corriente
sm2450.write(':SOUR:VOLT:RANG:AUTO ON') 
sm2450.write(':SENS:CURR:RANG:AUTO ON') 
sm2450.write(f":SOUR:VOLT:ILIM {i_limit}")
sm2450.write(f":SOUR:VOLT {v_start}")
sm2450.write(":OUTP ON")

# Preparamos la figura y la curva inicial
fig, ax = plt.subplots()
line, = ax.plot(measures[0,:], measures[1,:],'*', lw=2)
ax.set_xlabel('Voltaje (V)')
ax.set_ylabel('Corriente (A)')
ax.set_title('Curva I-V en tiempo real')
ax.grid(True)
plt.ion()  # modo interactivo
plt.show()

for i in range(np.shape(configured_voltages)[0]):
    # Cambiamos voltaje y adquirimos valor 
    sm2450.write(f":SOUR:VOLT {configured_voltages[i]}")
    sm2450.query("*OPC?") # Esperar a que termine la configuración
    measures[0,i]=sm2450.query(":MEAS:VOLT?")  # aquí ya haces query, no write+read
    measures[1,i]=sm2450.query(":MEAS:CURR?")
    sm2450.query("*OPC?") # Esperar a que termine la configuración
    
    # Actualizamos la figura / en principio el último valor 
    line.set_data(measures[0,0:i+1],measures[1,0:i+1])
    ax.relim()     # Si quieres puedes ajustar el eje Y dinámicamente:
    ax.autoscale_view()
    plt.pause(0.01)
    
plt.ioff()
plt.show()

#print(f"MEDICIÓN --> Voltaje= {voltaje.strip()} V, Corriente= {corriente.strip()} A")

# Apagar salida
sm2450.write(":OUTP OFF")

# Cerrar conexión
sm2450.close()
rm.close()