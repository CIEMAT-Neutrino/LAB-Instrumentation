import pyvisa #El generador utiliza el estándar USBTMC
rm = pyvisa.ResourceManager("@py") #Gestor de recursos que busca y abre instrumentos

gen = rm.open_resource("USB0::2391::22279::MY53801010::0::INSTR")
gen.timeout = 2000

try:
    print(gen.query("*IDN?"))
finally:
    gen.close()
