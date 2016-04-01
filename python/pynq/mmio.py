#   Copyright (c) 2016, Xilinx, Inc.
#   All rights reserved.
# 
#   Redistribution and use in source and binary forms, with or without 
#   modification, are permitted provided that the following conditions are met:
#
#   1.  Redistributions of source code must retain the above copyright notice, 
#       this list of conditions and the following disclaimer.
#
#   2.  Redistributions in binary form must reproduce the above copyright 
#       notice, this list of conditions and the following disclaimer in the 
#       documentation and/or other materials provided with the distribution.
#
#   3.  Neither the name of the copyright holder nor the names of its 
#       contributors may be used to endorse or promote products derived from 
#       this software without specific prior written permission.
#
#   THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#   AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, 
#   THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR 
#   PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR 
#   CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, 
#   EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, 
#   PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
#   OR BUSINESS INTERRUPTION). HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, 
#   WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR 
#   OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF 
#   ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

__author__      = "Yun Rock Qu"
__copyright__   = "Copyright 2016, Xilinx"
__email__       = "xpp_support@xilinx.com"


import os
import sys
import struct
import mmap
import math
from . import general_const

class MMIO:
    """ This class exposes API to carry MMIO operations.
    
    Attributes
    ----------
    base_addr : int
        The base address of the MMIO, aligned with pages.
    base_addr_offset : int
        The base address offset with respect to pages.
    length : int
        The length in bytes, with stop address aligned with words.
    debug : bool
        Turn on debug mode if it is True.
    mem : mmap
        An mmap object created when mapping files to memory.
    
    """

    def __init__(self, base_addr, length = 4, debug = False):
        """Return a new MMIO object.
        
        Parameters
        ----------
        base_addr : int
            The base address of the MMIO
        length : int
            The length in bytes; default is 4
        debug : bool
            Turn on debug mode if it is True; default is False
            
        """
        if base_addr < 0 or length < 0:
            raise ValueError("Negative offset or negative length.")
            
        euid = os.geteuid()
        if euid != 0:
            raise EnvironmentError('Root permissions required.')
        
        #: Align the base address with the pages
        self.base_addr = base_addr & ~(mmap.PAGESIZE - 1)
        #: Calculate base address offset w.r.t the base address
        self.base_addr_offset = base_addr - self.base_addr
        #: Align the stop address with the words
        stop = base_addr + length
        if (stop % general_const.MMIO_WORD_MASK):
            stop = (stop + general_const.MMIO_WORD_LENGTH) \
                    & general_const.MMIO_WORD_MASK
        #: Calculate the length between the base address and the stop address
        self.length = stop - self.base_addr
        
        self.debug = debug
        self._debug('MMIO(address, size) = ({0}, {1} bytes).'.
                format(hex(self.base_addr), hex(self.length)))
                
        #: Open file and mmap
        f = os.open(general_const.MMIO_FILE_NAME, os.O_RDWR | os.O_SYNC)
        self.mem = mmap.mmap(f, self.length, mmap.MAP_SHARED,
                    mmap.PROT_READ | mmap.PROT_WRITE,
                    offset = self.base_addr)

    def read(self, offset = 0, length = 4):
        """The method to read data from MMIO.
        
        Parameters
        ----------
        offset : int
            The offset added to the MMIO base address.
        length : int
            The length of the data in bytes.
        
        Returns
        -------
        list
            A list of data read out from MMIO
        
        """
        if offset < 0 or length < 0: 
            raise ValueError("Negative offset or negative length.")

        if offset + length > self.length:
            raise MemoryError('Read operation exceeds the MMIO length.')

        #: Make reading faster
        mem = self.mem

        self._debug('Reading {0} bytes from offset {1}'\
                    .format(length, hex(offset)))

        #: Compensate for the base_address and seek to the aligned offset
        virt_base_addr = self.base_addr_offset & general_const.MMIO_WORD_MASK
        mem.seek(virt_base_addr + offset)

        #: Read data out
        return (struct.unpack('I', mem.read(length))[0])


    def write(self, offset, data):
        """The method to write the data into MMIO.

        Parameters
        ----------
        offset : int
            The offset added to the MMIO base address.
        data : int / str
            The integer(s) to be written into MMIO.
        
        Returns
        -------
        None
        
        """
        if offset < 0: 
                raise ValueError("Negative offset.")
        
        if type(data) is int:
            if data > pow(2,32)-1:
                raise ValueError("Integer value is too large for a word.")
            length = 4
        elif (type(data) is str) or (type(data) is bytes):
            length = len(data)
        else:
            raise ValueError("Data types must be int, str, or bytes.")

        if offset + length > self.length:
                raise MemoryError('Write operation exceeds MMIO length.')
                
        # Make reading easier (and faster... won't resolve dot in loops)
        mem = self.mem

        # Compensate for the base_address
        offset += self.base_addr_offset

        # Check that the operation is going write to an aligned location
        if (offset & ~ general_const.MMIO_WORD_MASK): 
            raise MemoryError('Write operation not aligned.')

        # Seek to the aligned offset
        virt_base_addr = self.base_addr_offset & general_const.MMIO_WORD_MASK
        mem.seek(virt_base_addr + offset)

        if length == 4:
            self._debug('Writing 4 bytes to offset {0}: {1}'.\
                        format(hex(offset), hex(data)))
            mem.write(struct.pack('I', data))
        else:
            for i in range(0, length, general_const.MMIO_WORD_LENGTH):
                buf = int.from_bytes(data[i:i+general_const.MMIO_WORD_LENGTH],
                                     byteorder='little')
                mem.write(struct.pack('I', buf))

    def _debug(self, infor):
        """The method provides debug capabilities for this class.
        
        Parameters
        ----------
        infor : str
            The debug information
        
        Returns
        -------
        None
        
        """
        if self.debug: print('MMIO Debug: {0}'.format(infor))