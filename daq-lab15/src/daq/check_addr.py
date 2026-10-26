"""!
@file   check_addr.py
@brief  Quick communication check to see instrument addresses
"""
import pyvisa

rm = pyvisa.ResourceManager("@py") 
print(rm.list_resources())