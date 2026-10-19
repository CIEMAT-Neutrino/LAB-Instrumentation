import pyvisa # La fuente utiliza el estándar de puerto serie virtual CDC (TTY)
rm = pyvisa.ResourceManager("@py") #Gestor de recursos que busca y abre instrumentos

psu = rm.open_resource("ASRL/dev/ttyACM0::INSTR")
psu.baud_rate = 19200   # Según el manual
psu.read_termination = "\n"
psu.write_termination = "\n"
psu.timeout = 2000

try:
    print(psu.query("*IDN?"))
finally:
    psu.close()