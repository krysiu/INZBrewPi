from PyQt5.QtWidgets import QApplication, QMainWindow, QLCDNumber, QWidget, QCheckBox
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5 import QtGui, QtCore
from mainwindowinz import Ui_BrewPi
import sys
import os
import threading
import time
import RPi.GPIO as GPIO
import spidev
import logging


class ImageDialog(QMainWindow):
    signal = pyqtSignal(int)
    signal_cleaning = pyqtSignal(int)
    signal_temp_HTL = pyqtSignal(float)
    signal_temp_HTL2 = pyqtSignal(float)
    signal_temp_MASH = pyqtSignal(float)
    signal_temp_MASH2 = pyqtSignal(float)
    signal_temp_KETTLE = pyqtSignal(float)
    signal_temp_KETTLE2 = pyqtSignal(float)
    signal_time_KETTLE = pyqtSignal(float)

    timer = 0.001
    timer_c = 1
    cache_file = "settings"
    active_process = 1
    active_process_cleaning = 1
    end_program = False
    end_program_cleaning = False
    is_pause = False
    timer_worker_MASH = None
    timer_worker_MASH_2 = None
    timer_worker_MASH_OUT = None
    timer_worker_KETTLE = None
    pause_time = 0

    grzalka_HTL = 20
    grzalka_MASH = 18
    grzalka_KETTLE = 26
    buzzer = 19
    pompa_HTL_MASH = 12
    pompa_KETTLE = 6
    zawor_HTL_IN = 21
    zawor_HTL_OUT = 16
    zawor_MASH_IN = 25
    zawor_MASH_OUT = 24
    zawor_KETTLE_IN = 23
    zawor_KLA_KETTLE_OUT = 13
    zawor_KLA_KETTLE_IN = 5
    zawor_KETTLE_OUT = 22
    zawor_H2O_COOLER = 27
    logger = None

#Funkcja loggera wysyłającego komunikaty do konsoli oraz do pliku

    def set_logger(self):
        logPath = "log"
        fileName = time.strftime("%b %d %Y %H:%M:%S") + ".log"
        logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
        self.logger = logging.getLogger()
        if os.path.exists("log") is False:
            os.mkdir("log")

        fileHandler = logging.FileHandler(os.path.join(logPath, fileName))
        fileHandler.setFormatter(logFormatter)
        fileHandler.setLevel(logging.DEBUG)
        self.logger.addHandler(fileHandler)

        consoleHandler = logging.StreamHandler()
        consoleHandler.setFormatter(logFormatter)
        consoleHandler.setLevel(logging.DEBUG)
        self.logger.addHandler(consoleHandler)
        self.logger.setLevel(logging.DEBUG)


    def __init__(self):
        super(ImageDialog, self).__init__()
        self.set_logger()
        self.logger.info("Start interface")
        # Ustawienie interfejsu użytkownika z Designera.
        self.ui = Ui_BrewPi()
        self.ui.setupUi(self)
        self.ui.pushButtonStart.clicked.connect(self.start)
        self.ui.pushButton_start_clean.clicked.connect(self.cleaning)
        self.ui.pushButtonStop.clicked.connect(self.stop)
        self.ui.pushButton_stop_clean.clicked.connect(self.cleaning_stop)
        self.ui.pushButtonPause.clicked.connect(self.pause_event)
        self.ui.pushButton_pSTOP_ALL.clicked.connect(self.pompaSTOP_ALL)  # pauzuja tez proces
        self.ui.pushButton_zSTOP_ALL.clicked.connect(self.zaworSTOP_ALL)  # pauzuja tez proces

        self.ui.checkBox_zH2O_HTL.stateChanged.connect(self.changed_zH2O_HTL)
        self.ui.checkBox_zHTL_OUT.stateChanged.connect(self.changed_zHTL_OUT)
        self.ui.checkBox_zMASH_IN.stateChanged.connect(self.changed_zMASH_IN)
        self.ui.checkBox_zMASH_OUT.stateChanged.connect(self.changed_zMASH_OUT)
        self.ui.checkBox_zKETTLE_IN.stateChanged.connect(self.changed_zKETTLE_IN)
        self.ui.checkBox_zKETTLE_OUT.stateChanged.connect(self.changed_zKETTLE_OUT)
        self.ui.checkBox_zKLA_KETTLE_OUT.stateChanged.connect(self.changed_zKLA_KETTLE_OUT)
        self.ui.checkBox_zKLA_KETTLE_IN.stateChanged.connect(self.changed_zKLA_KETTLE_IN)
        self.ui.checkBox_zH2O_COOLER.stateChanged.connect(self.changed_zH2O_COOLER)
        self.ui.checkBox_pompa_HTL_MASH.stateChanged.connect(self.changed_pompa_HTL_MASH)
        self.ui.checkBox_pompa_KETTLE.stateChanged.connect(self.changed_pompa_KETTLE)

        self.readfromfile()
        self.ui.horizontalSlider_tempHTL.sliderReleased.connect(self.savetofile)
        self.ui.horizontalSlider_tempHTL2.sliderReleased.connect(self.savetofile)
        self.ui.horizontalSlider_tempMASH1_g.sliderReleased.connect(self.savetofile)
        self.ui.horizontalSlider_tempMASH1_d.sliderReleased.connect(self.savetofile)
        self.ui.horizontalSlider_tempMASH2_g.sliderReleased.connect(self.savetofile)
        self.ui.horizontalSlider_tempMASH2_d.sliderReleased.connect(self.savetofile)
        self.ui.horizontalSlider_tempMASH3_g.sliderReleased.connect(self.savetofile)
        self.ui.horizontalSlider_tempMASH3_d.sliderReleased.connect(self.savetofile)
        self.ui.horizontalSlider_tempKETTLE.sliderReleased.connect(self.savetofile)
        self.ui.horizontalSlider_tempKETTLE2.sliderReleased.connect(self.savetofile)
        self.ui.horizontalSlider_czasMASH1.sliderReleased.connect(self.savetofile)
        self.ui.horizontalSlider_czasMASH2.sliderReleased.connect(self.savetofile)
        self.ui.horizontalSlider_czasMASH3.sliderReleased.connect(self.savetofile)
        self.ui.horizontalSlider_czasKETTLE.sliderReleased.connect(self.savetofile)

    #Zapisuję ostanie ustawienia do pliku 'settings'
    def savetofile(self):

        with open(self.cache_file, 'w') as file_:
            file_.write(self.ui.label_value_tempHTL.text() + '\n')
            file_.write(self.ui.label_value_tempHTL2.text() + '\n')
            file_.write(self.ui.label_value_tempMASH1_g.text() + '\n')
            file_.write(self.ui.label_value_tempMASH1_d.text() + '\n')
            file_.write(self.ui.label_value_tempMASH2_g.text() + '\n')
            file_.write(self.ui.label_value_tempMASH2_d.text() + '\n')
            file_.write(self.ui.label_value_tempMASH3_g.text() + '\n')
            file_.write(self.ui.label_value_tempMASH3_d.text() + '\n')
            file_.write(self.ui.label_value_tempKETTLE.text() + '\n')
            file_.write(self.ui.label_value_tempKETTLE2.text() + '\n')
            file_.write(self.ui.label_value_czasMASH1.text() + '\n')
            file_.write(self.ui.label_value_czasMASH2.text() + '\n')
            file_.write(self.ui.label_value_czasMASH3.text() + '\n')
            file_.write(self.ui.label_value_czasKETTLE.text() + '\n')

    #Jeżeli plik 'settings' istnieje odczytuję z niego ostanio użyte ustawienia
    def readfromfile(self):
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r') as file_:
                self.ui.label_value_tempHTL.setText(file_.readline().replace("\n", ""))
                self.ui.horizontalSlider_tempHTL.setSliderPosition(int(self.ui.label_value_tempHTL.text()))

                self.ui.label_value_tempHTL2.setText(file_.readline().replace("\n", ""))
                self.ui.horizontalSlider_tempHTL2.setSliderPosition(int(self.ui.label_value_tempHTL2.text()))

                self.ui.label_value_tempMASH1_g.setText(file_.readline().replace("\n", ""))
                self.ui.horizontalSlider_tempMASH1_g.setSliderPosition(int(self.ui.label_value_tempMASH1_g.text()))

                self.ui.label_value_tempMASH1_d.setText(file_.readline().replace("\n", ""))
                self.ui.horizontalSlider_tempMASH1_d.setSliderPosition(int(self.ui.label_value_tempMASH1_d.text()))

                self.ui.label_value_tempMASH2_g.setText(file_.readline().replace("\n", ""))
                self.ui.horizontalSlider_tempMASH2_g.setSliderPosition(int(self.ui.label_value_tempMASH2_g.text()))

                self.ui.label_value_tempMASH2_d.setText(file_.readline().replace("\n", ""))
                self.ui.horizontalSlider_tempMASH2_d.setSliderPosition(int(self.ui.label_value_tempMASH2_d.text()))

                self.ui.label_value_tempMASH3_g.setText(file_.readline().replace("\n", ""))
                self.ui.horizontalSlider_tempMASH3_g.setSliderPosition(int(self.ui.label_value_tempMASH3_g.text()))

                self.ui.label_value_tempMASH3_d.setText(file_.readline().replace("\n", ""))
                self.ui.horizontalSlider_tempMASH3_d.setSliderPosition(int(self.ui.label_value_tempMASH3_d.text()))

                self.ui.label_value_tempKETTLE.setText(file_.readline().replace("\n", ""))
                self.ui.horizontalSlider_tempKETTLE.setSliderPosition(int(self.ui.label_value_tempKETTLE.text()))

                self.ui.label_value_tempKETTLE2.setText(file_.readline().replace("\n", ""))
                self.ui.horizontalSlider_tempKETTLE2.setSliderPosition(int(self.ui.label_value_tempKETTLE2.text()))

                self.ui.label_value_czasMASH1.setText(file_.readline().replace("\n", ""))
                self.ui.horizontalSlider_czasMASH1.setSliderPosition(int(self.ui.label_value_czasMASH1.text()))

                self.ui.label_value_czasMASH2.setText(file_.readline().replace("\n", ""))
                self.ui.horizontalSlider_czasMASH2.setSliderPosition(int(self.ui.label_value_czasMASH2.text()))

                self.ui.label_value_czasMASH3.setText(file_.readline().replace("\n", ""))
                self.ui.horizontalSlider_czasMASH3.setSliderPosition(int(self.ui.label_value_czasMASH3.text()))

                self.ui.label_value_czasKETTLE.setText(file_.readline().replace("\n", ""))
                self.ui.horizontalSlider_czasKETTLE.setSliderPosition(int(self.ui.label_value_czasKETTLE.text()))


    #funkncja startująca program po wcisnieciu przycisku 'start'
    def start(self):
        self.logger.info("Start process")
        self.ui.pushButtonPause.setEnabled(True)
        self.ui.pushButtonStop.setEnabled(True)
        self.ui.pushButtonStart.setEnabled(False)
        self.end_program = False
        if self.is_pause:
            self.is_pause = False
        else:
            self.active_process = 1
            self.timer_worker_MASH = None
            self.timer_worker_MASH_2 = None
            self.timer_worker_MASH_OUT = None
            self.timer_worker_KETTLE = None
            self.pause_time = 0
            self.signal.emit(0)

            GPIO.setmode(GPIO.BCM)  # choose BCM or BOARD
            GPIO.setup(self.grzalka_HTL, GPIO.OUT)  # grzałka HTL
            GPIO.setup(self.grzalka_MASH, GPIO.OUT)  # grzałka MASH
            GPIO.setup(self.grzalka_KETTLE, GPIO.OUT)  # grzałka KETTLE
            GPIO.setup(self.buzzer, GPIO.OUT)  # buzzer (KETTLE)
            GPIO.setup(self.pompa_HTL_MASH, GPIO.OUT)  # pompa 1
            GPIO.setup(self.pompa_KETTLE, GPIO.OUT)  # pompa 2
            GPIO.setup(self.zawor_HTL_IN, GPIO.OUT)  # zawór 1 (nalewanie wody do HTL)
            GPIO.setup(self.zawor_HTL_OUT, GPIO.OUT)  # zawór 2
            GPIO.setup(self.zawor_MASH_IN, GPIO.OUT)  # zawór 3
            GPIO.setup(self.zawor_MASH_OUT, GPIO.OUT)  # zawór 4
            GPIO.setup(self.zawor_KETTLE_IN, GPIO.OUT)  # zawór 5
            GPIO.setup(self.zawor_KLA_KETTLE_OUT, GPIO.OUT)  # zawór 6
            GPIO.setup(self.zawor_KLA_KETTLE_IN, GPIO.OUT)  # zawór 7
            GPIO.setup(self.zawor_KETTLE_OUT, GPIO.OUT)  # zawór 8
            GPIO.setup(self.zawor_H2O_COOLER, GPIO.OUT)  # zawór 9

            # Ustawienie urzadzeń SPI na Bus 0,Device 0
            self.spi = spidev.SpiDev()
            self.spi.open(0, 0)
            # Załadowanie 1-wire
            os.system('modprobe w1-gpio')
            os.system('modprobe w1-therm')
            # zmienne termometrow
            self.base_dir = '/sys/bus/w1/devices/'
            self.device_folder_HTL = '/sys/bus/w1/devices/28-02155270d3ff'
            self.device_folder_HTL2 = '/sys/bus/w1/devices/28-0215535c29ff'
            self.device_file_HTL = self.device_folder_HTL + '/w1_slave'
            self.device_file_HTL2 = self.device_folder_HTL2 + '/w1_slave'
            self.device_folder_MASH = '/sys/bus/w1/devices/28-02155270d3ff'  # wstawic numer temometru
            self.device_folder_MASH2 = '/sys/bus/w1/devices/28-0215535c29ff'  # wstawic numer temometru
            self.device_file_MASH = self.device_folder_MASH + '/w1_slave'
            self.device_file_MASH2 = self.device_folder_MASH2 + '/w1_slave'
            self.device_folder_KETTLE = '/sys/bus/w1/devices/28-02155270d3ff'  # wstawic numer temometru
            self.device_folder_KETTLE2 = '/sys/bus/w1/devices/28-0215535c29ff'  # wstawic numer temometru
            self.device_file_KETTLE = self.device_folder_KETTLE + '/w1_slave'
            self.device_file_KETTLE2 = self.device_folder_KETTLE2 + '/w1_slave'
            #połączenie sygnałow z interefsjem
            self.signal.connect(self.ui.progressBar.setValue)
            self.signal_temp_HTL.connect(self.ui.lcd_HTL.display)
            self.signal_temp_HTL2.connect(self.ui.lcd_HTL2.display)
            self.signal_temp_MASH.connect(self.ui.lcd_MASH.display)
            self.signal_temp_MASH2.connect(self.ui.lcd_MASH2.display)
            self.signal_temp_KETTLE.connect(self.ui.lcd_KETTLE.display)
            self.signal_temp_KETTLE2.connect(self.ui.lcd_KETTLE2.display)
            self.signal_time_KETTLE.connect(self.ui.lcd_time_KETTLE.display)
            #start wątku funkcja background_process
            threading.Thread(target=self.background_process).start()

    def background_process(self):
        while self.end_program is False:
            time.sleep(self.timer)

            if self.is_pause is True:
                self.pause()
            else:
                self.update_temp()

                self.getAdc_HTL(0)
                self.worker_HTL()
                self.worker_HTL_continue()
                self.getAdc_MASH(1)
                self.worker_MASH()
                self.worker_MASH_2()
                self.worker_MASH_OUT()
                self.getAdc_KETTLE(2)
                self.worker_KETTLE()
                self.getAdc_KETTLE_out(2)

    #Funkcja zdarzenia powodującego pauze
    def pause_event(self):
        self.ui.pushButtonStart.setEnabled(True)
        self.ui.pushButtonStop.setEnabled(True)
        self.ui.pushButtonPause.setEnabled(False)
        self.is_pause = True

    #Funkcja Pauza wstrzymuje proces
    def pause(self):
        self.logger.info("Process paused")
        start = time.time()
        while self.is_pause:
            time.sleep(0.01)
            delta = time.time() - start
            self.pause_time += delta

    #Funkcja stopu
    def stop(self):
        self.logger.info("Process stoped")
        self.ui.pushButtonStart.setEnabled(True)
        self.ui.pushButtonStop.setEnabled(False)
        self.ui.pushButtonPause.setEnabled(False)

        self.ui.checkBox_zH2O_HTL.setChecked(False)
        self.ui.checkBox_zHTL_OUT.setChecked(False)
        self.ui.checkBox_zMASH_IN.setChecked(False)
        self.ui.checkBox_zMASH_OUT.setChecked(False)
        self.ui.checkBox_zKETTLE_IN.setChecked(False)
        self.ui.checkBox_zKETTLE_OUT.setChecked(False)
        self.ui.checkBox_zKLA_KETTLE_OUT.setChecked(False)
        self.ui.checkBox_zKLA_KETTLE_IN.setChecked(False)
        self.ui.checkBox_zH2O_COOLER.setChecked(False)
        self.ui.checkBox_pompa_HTL_MASH.setChecked(False)
        self.ui.checkBox_pompa_KETTLE.setChecked(False)
        self.end_program = True
        self.is_pause = False
        pass

    #Sygnal emituję wartości funcji odczytu temeperatury
    def update_temp(self):
        self.signal_temp_HTL.emit(self.read_temp_HTL())
        self.signal_temp_HTL2.emit(self.read_temp_HTL2())
        self.signal_temp_MASH.emit(self.read_temp_MASH())
        self.signal_temp_MASH2.emit(self.read_temp_MASH2())
        self.signal_temp_KETTLE.emit(self.read_temp_KETTLE())
        self.signal_temp_KETTLE2.emit(self.read_temp_KETTLE2())

#Funkcję odpowiedzialne za działanie programu do produkcji piwa

    # Funkcja czujnika cisnienia i sterowanie zaworem HTL
    def getAdc_HTL(self, channel):
        if self.active_process == 1:

            # sprawdza czy dobry kanał
            if ((channel > 7) or (channel < 0)):
                self.logger.error("Wrong channel on ADC")
                return

                # Preform SPI transaction and store returned bits in 'r'

            r = self.spi.xfer([1, (8 + channel) << 4, 0])

            # Filter data bits from retruned bits

            adcOut = ((r[1] & 3) << 8) + r[2]
            percent = int(round(adcOut / 10.24))

            if (percent <= 80):
                self.ui.checkBox_zH2O_HTL.setChecked(True)
                GPIO.output(self.zawor_HTL_IN, True)
            else:
                self.ui.checkBox_zH2O_HTL.setChecked(False)
                GPIO.output(self.zawor_HTL_IN, False)
                self.signal.emit(10)
                self.active_process = 2
                self.logger.info("Filling HTL [pass]") # koniec pierwszego watku (napelniania zbiornika) emisja sygnalu i wartosci ile % zostalo ukonczon


    def read_temp_HTL(self):
        tempfile = open(self.device_file_HTL)
        thetext = tempfile.read()
        tempfile.close()
        tempdata = thetext.split("\n")[1].split(" ")[9]
        temperat = float(tempdata[2:])
        temperature = temperat / 1000
        return temperature

    def read_temp_HTL2(self):
        tempfile = open(self.device_file_HTL2)
        thetext = tempfile.read()
        tempfile.close()
        tempdata = thetext.split("\n")[1].split(" ")[9]
        temperat = float(tempdata[2:])
        temperature = temperat / 1000
        return temperature

    #Grzanie wody w HTL
    def worker_HTL(self):
        if self.active_process == 2:
            t1 = self.ui.lcd_HTL.intValue()
            t2 = self.ui.lcd_HTL2.intValue()
            if t1 < int(self.ui.label_value_tempHTL.text()) and t2 < int(self.ui.label_value_tempHTL2.text()):
                GPIO.output(self.grzalka_HTL, True)
            else:
                self.logger.warning("Temperature HTL too high")
                GPIO.output(self.grzalka_HTL, False)
                self.signal.emit(20)
                self.active_process = 3


    def getAdc_MASH(self, channel):  # f. napelniania MASH
        if self.active_process == 3:
        #check valid channel

            if ((channel>7)or(channel<0)):
                self.logger.error("Wrong channel on ADC")
                return

        # Preform SPI transaction and store returned bits in 'r'

            r = self.spi.xfer([1, (8+channel) << 4, 0])

        #Filter data bits from retruned bits

            adcOut = ((r[1] & 3) << 8) + r[2]
            percent = int(round(adcOut/10.24))

            if (percent <= 80):
                self.ui.checkBox_zHTL_OUT.setChecked(True)
                self.ui.checkBox_pompa_HTL_MASH.setChecked(True)
                self.ui.checkBox_zMASH_IN.setChecked(True)
                GPIO.output(self.zawor_HTL_OUT, True)
                GPIO.output(self.pompa_HTL_MASH, True)
                GPIO.output(self.zawor_MASH_IN, True)
            else:
                self.ui.checkBox_zHTL_OUT.setChecked(False)
                self.ui.checkBox_pompa_HTL_MASH.setChecked(False)
                self.ui.checkBox_zMASH_IN.setChecked(False)
                GPIO.output(self.zawor_HTL_OUT, False)
                GPIO.output(self.pompa_HTL_MASH, False)
                GPIO.output(self.zawor_MASH_IN, False)
                self.signal.emit(30)
                self.active_process = 4
                self.logger.info("Filling MASH [pass]")


    def read_temp_MASH(self):
        tempfile = open(self.device_file_MASH)
        thetext = tempfile.read()
        tempfile.close()
        tempdata = thetext.split("\n")[1].split(" ")[9]
        temperat = float(tempdata[2:])
        temperature = temperat / 1000
        return temperature

    def read_temp_MASH2(self):
        tempfile = open(self.device_file_MASH2)
        thetext = tempfile.read()
        tempfile.close()
        tempdata = thetext.split("\n")[1].split(" ")[9]
        temperat = float(tempdata[2:])
        temperature = temperat / 1000
        return temperature


    def worker_MASH(self):
        if self.active_process == 4:
            if self.timer_worker_MASH is None:
                self.timer_worker_MASH = time.time()

            time_heat = int(self.ui.label_value_czasMASH1.text())
            t1 = self.ui.lcd_MASH.intValue()
            t2 = self.ui.lcd_MASH2.intValue()
            if time.time() - (self.timer_worker_MASH + self.pause_time) <= time_heat:
                if t1 < int(self.ui.label_value_tempMASH1_d.text()) and t2 < int(self.ui.label_value_tempMASH1_g.text()):
                    GPIO.output(self.grzalka_MASH, True)
                    GPIO.output(self.zawor_MASH_OUT, True)
                    GPIO.output(self.zawor_MASH_IN, True)
                    GPIO.output(self.pompa_HTL_MASH, True)
                else:
                    GPIO.output(self.grzalka_MASH, False)
                    GPIO.output(self.zawor_MASH_OUT, True)
                    GPIO.output(self.zawor_MASH_IN, True)
                    GPIO.output(self.pompa_HTL_MASH, True)
                    self.logger.warning("Temperature MASH too high")
            else:
                self.signal.emit(30)
                self.active_process = 5

    def worker_MASH_2(self):
        if self.active_process == 5:
            if self.timer_worker_MASH_2 is None:
                self.timer_worker_MASH_2 = time.time()

            time_heat = int(self.ui.label_value_czasMASH2.text())
            t1 = self.ui.lcd_MASH.intValue()
            t2 = self.ui.lcd_MASH2.intValue()
            if time.time() - (self.timer_worker_MASH_2 + self.pause_time) <= time_heat:
                if t1 < int(self.ui.label_value_tempMASH2_d.text()) and t2 < int(self.ui.label_value_tempMASH2_g.text()):
                    GPIO.output(self.grzalka_MASH, True)
                    GPIO.output(self.zawor_MASH_OUT, True)
                    GPIO.output(self.zawor_MASH_IN, True)
                    GPIO.output(self.pompa_HTL_MASH, True)
                else:
                    GPIO.output(self.grzalka_MASH, False)
                    GPIO.output(self.zawor_MASH_OUT, True)
                    GPIO.output(self.zawor_MASH_IN, True)
                    GPIO.output(self.pompa_HTL_MASH, True)
                    self.logger.warning("Temperature MASH_2 too high")
            else:
                self.signal.emit(40)
                self.active_process = 6

    def worker_MASH_OUT(self):
        if self.active_process == 6:
            if self.timer_worker_MASH_OUT is None:
                self.timer_worker_MASH_OUT = time.time()

            time_heat = int(self.ui.label_value_czasMASH3.text())
            t1 = self.ui.lcd_MASH.intValue()
            t2 = self.ui.lcd_MASH2.intValue()
            if time.time() - (self.timer_worker_MASH_OUT + self.pause_time) <= time_heat:
                if t1 < int(self.ui.label_value_tempMASH3_d.text()) and t2 < int(self.ui.label_value_tempMASH3_g.text()):
                    GPIO.output(self.grzalka_MASH, True)
                    GPIO.output(self.zawor_MASH_OUT, True)
                    GPIO.output(self.zawor_MASH_IN, True)
                    GPIO.output(self.pompa_HTL_MASH, True)
                else:
                    GPIO.output(self.grzalka_MASH, False)
                    GPIO.output(self.zawor_MASH_OUT, True)
                    GPIO.output(self.zawor_MASH_IN, True)  #sprawidzic czy nie ma odbywac sie w syrkulacji jezlei nie wywali zawory i pompe
                    GPIO.output(self.pompa_HTL_MASH, True)
                    self.logger.warning("Temperature MASH_OUT too high")
            else:
                GPIO.output(self.zawor_MASH_OUT, False)
                GPIO.output(self.pompa_HTL_MASH, False)
                GPIO.output(self.zawor_MASH_IN, False)
                self.signal.emit(50)
                self.active_process = 7


    def getAdc_KETTLE(self, channel):  # f. napelniania KETTLE
        if self.active_process == 7:
        #check valid channel

            if ((channel>7)or(channel<0)):
                self.logger.error("Wrong channel on ADC")
                return

        # Preform SPI transaction and store returned bits in 'r'

            r = self.spi.xfer([1, (8+channel) << 4, 0])

        #Filter data bits from retruned bits

            adcOut = ((r[1] & 3) << 8) + r[2]
            percent = int(round(adcOut/10.24))

            if (percent < 80):  # opróżnienie
                self.ui.checkBox_zMASH_OUT.setChecked(True)
                self.ui.checkBox_pompa_HTL_MASH.setChecked(True)
                self.ui.checkBox_zKETTLE_IN.setChecked(True)
                GPIO.output(self.zawor_MASH_OUT, True)
                GPIO.output(self.pompa_HTL_MASH, True)
                GPIO.output(self.zawor_KETTLE_IN, True)

            else:
                self.ui.checkBox_zMASH_OUT.setChecked(False)
                self.ui.checkBox_pompa_HTL_MASH.setChecked(False)
                self.ui.checkBox_zKETTLE_IN.setChecked(False)
                GPIO.output(self.zawor_MASH_OUT, False)
                GPIO.output(self.pompa_HTL_MASH, False)
                GPIO.output(self.zawor_KETTLE_IN, False)
                self.signal.emit(60)
                self.active_process = 8
                self.logger.info("Filling KETTLE [pass]")


    def read_temp_KETTLE(self):
        tempfile = open(self.device_file_KETTLE)
        thetext = tempfile.read()
        tempfile.close()
        tempdata = thetext.split("\n")[1].split(" ")[9]
        temperat = float(tempdata[2:])
        temperature = temperat / 1000
        return temperature

    def read_temp_KETTLE2(self):
        tempfile = open(self.device_file_KETTLE2)
        thetext = tempfile.read()
        tempfile.close()
        tempdata = thetext.split("\n")[1].split(" ")[9]
        temperat = float(tempdata[2:])
        temperature = temperat / 1000
        return temperature


    def worker_KETTLE(self):
        if self.active_process == 8:
            if self.timer_worker_KETTLE is None:
                self.timer_worker_KETTLE = time.time()
            time_heat = int(self.ui.label_value_czasKETTLE.text())

            t1 = self.ui.lcd_KETTLE.intValue()
            t2 = self.ui.lcd_KETTLE2.intValue()
            duration = time.time() - (self.timer_worker_KETTLE + self.pause_time)
            self.signal_time_KETTLE.emit(duration)
            if duration <= time_heat:
                if t1 < int(self.ui.label_value_tempKETTLE.text()) and t2 < int(self.ui.label_value_tempKETTLE2.text()) and int(duration) != 40 and int(duration) != 80:
                    GPIO.output(self.grzalka_KETTLE, True)
                elif t1 <= int(self.ui.label_value_tempKETTLE.text()) and t2 <= int(self.ui.label_value_tempKETTLE2.text()) and int(duration) == 40:  # pomyslec co bedzie gdy akurat przekroczy o 1-2 stopnie!!
                    GPIO.output(self.buzzer, True)
                elif t1 <= int(self.ui.label_value_tempKETTLE.text()) and t2 <= int(self.ui.label_value_tempKETTLE2.text()) and int(duration) == 80:
                    GPIO.output(self.buzzer, True)
                elif t1 < int(self.ui.label_value_tempKETTLE.text()) and t2 < int(self.ui.label_value_tempKETTLE2.text()) and int(duration) == int(0.8*duration):
                    self.ui.checkBox_zKLA_KETTLE_OUT.setChecked(True)
                    self.ui.checkBox_zKLA_KETTLE_IN.setChecked(True)
                    self.ui.checkBox_pompa_KETTLE.setChecked(True)
                    GPIO.output(self.grzalka_KETTLE, True)
                    GPIO.output(self.zawor_KLA_KETTLE_OUT, True)
                    GPIO.output(self.zawor_KLA_KETTLE_IN, True)
                    GPIO.output(self.pompa_KETTLE, True)
                else:
                    self.ui.checkBox_zKLA_KETTLE_OUT.setChecked(False)
                    self.ui.checkBox_zKLA_KETTLE_IN.setChecked(False)
                    self.ui.checkBox_pompa_KETTLE.setChecked(False)
                    GPIO.output(self.grzalka_KETTLE, False)
                    GPIO.output(self.zawor_KLA_KETTLE_OUT, False)
                    GPIO.output(self.pompa_KETTLE, False)
                    self.logger.warning("Temperature MASH_OUT too high")

            else:
                GPIO.output(self.buzzer, True)
                self.signal.emit(85)
                self.active_process = 9


    def getAdc_KETTLE_out(self, channel):  # f. oprozniania KETTLE
        if self.active_process == 9:
        #check valid channel

            if ((channel>7)or(channel<0)):
                self.logger.error("Wrong channel on ADC")
                return

        # Preform SPI transaction and store returned bits in 'r'

            r = self.spi.xfer([1, (8+channel) << 4, 0])

        #Filter data bits from retruned bits

            adcOut = ((r[1] & 3) << 8) + r[2]
            percent = int(round(adcOut/10.24))

            if (percent > 0):   # oproznianie (dziala dopoki nie bedzie 0%)
                self.ui.checkBox_zH2O_COOLER.setChecked(True)
                self.ui.checkBox_zKLA_KETTLE_OUT.setChecked(True)
                GPIO.output(self.zawor_H2O_COOLER, True)
                GPIO.output(self.zawor_KETTLE_OUT, True)
            else:
                self.ui.checkBox_zH2O_COOLER.setChecked(False)
                self.ui.checkBox_zKLA_KETTLE_OUT.setChecked(False)
                GPIO.output(self.zawor_KETTLE_OUT, False)
                GPIO.output(self.zawor_H2O_COOLER, False)
                self.signal.emit(100)
                self.active_process = 10
                self.logger.info("Emptying KETTLE [pass]")

    #Cały czas podgrzewa wodę w HTL i dopełnia KETTLE po zacieraniu
    def worker_HTL_continue(self):
        if self.active_process == 3 or self.active_process == 4 or self.active_process == 5 or self.active_process == 6:
            t2 = self.ui.lcd_HTL2.intValue()
            if t2 < int(self.ui.label_value_tempMASH3_g.text()):
                GPIO.output(self.grzalka_HTL, True)
        elif self.active_process == 7:
            time.sleep(10)
            GPIO.output(self.zawor_HTL_OUT, True)
        else:
            GPIO.output(self.zawor_HTL_OUT, False)


    # Funkcję zakładki 'zawory i pompy' awaryjnę zamkniecie pomp i zaworów
    def zaworSTOP_ALL(self):
        self.ui.pushButtonStart.setEnabled(True)
        self.ui.pushButtonStop.setEnabled(True)
        self.ui.pushButtonPause.setEnabled(False)
        self.is_pause = True

        self.ui.checkBox_zH2O_HTL.setChecked(False)
        GPIO.output(self.zawor_HTL_IN, False)
        self.ui.checkBox_zHTL_OUT.setChecked(False)
        GPIO.output(self.zawor_HTL_OUT, False)
        self.ui.checkBox_zMASH_IN.setChecked(False)
        GPIO.output(self.zawor_MASH_IN, False)
        self.ui.checkBox_zMASH_OUT.setChecked(False)
        GPIO.output(self.zawor_MASH_OUT, False)
        self.ui.checkBox_zKETTLE_IN.setChecked(False)
        GPIO.output(self.zawor_KETTLE_IN, False)
        self.ui.checkBox_zKETTLE_OUT.setChecked(False)
        GPIO.output(self.zawor_KETTLE_OUT, False)
        self.ui.checkBox_zKLA_KETTLE_OUT.setChecked(False)
        GPIO.output(self.zawor_KLA_KETTLE_OUT, False)
        self.ui.checkBox_zKLA_KETTLE_IN.setChecked(False)
        GPIO.output(self.zawor_KLA_KETTLE_IN, False)
        self.ui.checkBox_zH2O_COOLER.setChecked(False)
        GPIO.output(self.zawor_H2O_COOLER, False)

    def pompaSTOP_ALL(self):
        self.ui.pushButtonStart.setEnabled(True)
        self.ui.pushButtonStop.setEnabled(True)
        self.ui.pushButtonPause.setEnabled(False)
        self.is_pause = True

        self.ui.checkBox_pompa_HTL_MASH.setChecked(False)
        GPIO.output(self.pompa_HTL_MASH, False)
        self.ui.checkBox_pompa_KETTLE.setChecked(False)
        GPIO.output(self.pompa_KETTLE, False)


    def changed_zH2O_HTL(self, state):
        if state == Qt.Checked:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.zawor_HTL_IN, GPIO.OUT)
            GPIO.output(self.zawor_HTL_IN, True)
        else:
            GPIO.output(self.zawor_HTL_IN, False)

    def changed_zHTL_OUT(self, state):
        if state == Qt.Checked:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.zawor_HTL_OUT, GPIO.OUT)
            GPIO.output(self.zawor_HTL_OUT, True)
        else:
            GPIO.output(self.zawor_HTL_OUT, False)

    def changed_zMASH_IN(self, state):
        if state == Qt.Checked:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.zawor_MASH_IN, GPIO.OUT)
            GPIO.output(self.zawor_MASH_IN, True)
        else:
            GPIO.output(self.zawor_MASH_IN, False)

    def changed_zMASH_OUT(self, state):
        if state == Qt.Checked:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.zawor_MASH_OUT, GPIO.OUT)
            GPIO.output(self.zawor_MASH_OUT, True)
        else:
            GPIO.output(self.zawor_MASH_OUT, False)

    def changed_zKETTLE_IN(self, state):
        if state == Qt.Checked:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.zawor_KETTLE_IN, GPIO.OUT)
            GPIO.output(self.zawor_KETTLE_IN, True)
        else:
            GPIO.output(self.zawor_KETTLE_IN, False)

    def changed_zKETTLE_OUT(self, state):
        if state == Qt.Checked:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.zawor_KETTLE_OUT, GPIO.OUT)
            GPIO.output(self.zawor_KETTLE_OUT, True)
        else:
            GPIO.output(self.zawor_KETTLE_OUT, False)

    def changed_zKLA_KETTLE_OUT(self, state):
        if state == Qt.Checked:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.zawor_KLA_KETTLE_OUT, GPIO.OUT)
            GPIO.output(self.zawor_KLA_KETTLE_OUT, True)
        else:
            GPIO.output(self.zawor_KLA_KETTLE_OUT, False)

    def changed_zKLA_KETTLE_IN(self, state):
        if state == Qt.Checked:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.zawor_KLA_KETTLE_IN, GPIO.OUT)
            GPIO.output(self.zawor_KLA_KETTLE_IN, True)
        else:
            GPIO.output(self.zawor_KLA_KETTLE_IN, False)

    def changed_zH2O_COOLER(self, state):
        if state == Qt.Checked:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.zawor_H2O_COOLER, GPIO.OUT)
            GPIO.output(self.zawor_H2O_COOLER, True)
        else:
            GPIO.output(self.zawor_H2O_COOLER, False)

    def changed_pompa_HTL_MASH(self, state):
        if state == Qt.Checked:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pompa_HTL_MASH, GPIO.OUT)
            GPIO.output(self.pompa_HTL_MASH, True)
        else:
            GPIO.output(self.pompa_HTL_MASH, False)


    def changed_pompa_KETTLE(self, state):
        if state == Qt.Checked:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pompa_KETTLE, GPIO.OUT)
            GPIO.output(self.pompa_KETTLE, True)
        else:
            GPIO.output(self.pompa_KETTLE, False)


    #Program czyszczenia
    def cleaning(self):
        self.active_process_cleaning = 1
        self.ui.pushButton_start_clean.setEnabled(False)
        self.ui.pushButton_stop_clean.setEnabled(True)
        self.end_program_cleaning = False
        self.signal_cleaning.emit(0)
        self.logger.info("Start cleaning process")

        GPIO.setmode(GPIO.BCM)  # choose BCM or BOARD
        GPIO.setup(self.grzalka_HTL, GPIO.OUT)  # grzałka HTL
        GPIO.setup(self.pompa_HTL_MASH, GPIO.OUT)  # pompa 1
        GPIO.setup(self.pompa_KETTLE, GPIO.OUT)  # pompa 2
        GPIO.setup(self.zawor_HTL_IN, GPIO.OUT)  # zawór 1 (nalewanie wody do HTL)
        GPIO.setup(self.zawor_HTL_OUT, GPIO.OUT)  # zawór 2
        GPIO.setup(self.zawor_MASH_IN, GPIO.OUT)  # zawór 3
        GPIO.setup(self.zawor_MASH_OUT, GPIO.OUT)  # zawór 4
        GPIO.setup(self.zawor_KETTLE_IN, GPIO.OUT)  # zawór 5
        GPIO.setup(self.zawor_KLA_KETTLE_OUT, GPIO.OUT)  # zawór 6
        GPIO.setup(self.zawor_KLA_KETTLE_IN, GPIO.OUT)  # zawór 7
        GPIO.setup(self.zawor_KETTLE_OUT, GPIO.OUT)  # zawór 8
        GPIO.setup(self.zawor_H2O_COOLER, GPIO.OUT)  # zawór 9

        # Establish SPI device on Bus 0,Device 0
        self.spi = spidev.SpiDev()
        self.spi.open(0, 0)
        # Loaded 1-wire
        os.system('modprobe w1-gpio')
        os.system('modprobe w1-therm')
        # zmienne termometrow
        self.base_dir = '/sys/bus/w1/devices/'
        self.device_folder_HTL = '/sys/bus/w1/devices/28-02155270d3ff'
        self.device_folder_HTL2 = '/sys/bus/w1/devices/28-0215535c29ff'
        self.device_file_HTL = self.device_folder_HTL + '/w1_slave'
        self.device_file_HTL2 = self.device_folder_HTL2 + '/w1_slave'
        self.signal_cleaning.connect(self.ui.progressBar_clean_process.setValue)
        self.signal_temp_HTL.connect(self.ui.lcd_HTL.display)
        self.signal_temp_HTL2.connect(self.ui.lcd_HTL2.display)

        threading.Thread(target=self.background_cleaning_process).start()

    def background_cleaning_process(self):
        while self.end_program_cleaning is False:
            time.sleep(self.timer_c)
            self.getAdc_HTL_cleaning(0)
            self.worker_HTL_cleaning()
            self.getAdc_MASH_cleaning(1)
            self.getAdc_KETTLE_cleaning(2)
            self.getAdc_KETTLE_out_cleaning(2)

    def cleaning_stop(self):
        self.ui.pushButton_start_clean.setEnabled(True)
        self.ui.pushButton_stop_clean.setEnabled(False)
        self.end_program_cleaning = True

        self.ui.checkBox_zH2O_HTL.setChecked(False)
        self.ui.checkBox_zHTL_OUT.setChecked(False)
        self.ui.checkBox_zMASH_IN.setChecked(False)
        self.ui.checkBox_zMASH_OUT.setChecked(False)
        self.ui.checkBox_zKETTLE_IN.setChecked(False)
        self.ui.checkBox_zKETTLE_OUT.setChecked(False)
        self.ui.checkBox_zKLA_KETTLE_OUT.setChecked(False)
        self.ui.checkBox_zKLA_KETTLE_IN.setChecked(False)
        self.ui.checkBox_zH2O_COOLER.setChecked(False)

        self.ui.checkBox_pompa_HTL_MASH.setChecked(False)
        self.ui.checkBox_pompa_KETTLE.setChecked(False)

    def getAdc_HTL_cleaning(self, channel):
        if self.active_process_cleaning == 1:
        #check valid channel

            if ((channel>7)or(channel<0)):
                self.logger.error("Wrong channel on ADC")
                return

        # Preform SPI transaction and store returned bits in 'r'

            r = self.spi.xfer([1, (8+channel) << 4, 0])

        #Filter data bits from retruned bits

            adcOut = ((r[1] & 3) << 8) + r[2]
            percent = int(round(adcOut/10.24))

            if (percent <= 80):
                self.ui.checkBox_zH2O_HTL.setChecked(True)
                GPIO.output(self.zawor_HTL_IN, True)
            else:
                self.ui.checkBox_zH2O_HTL.setChecked(False)
                GPIO.output(self.zawor_HTL_IN, False)
                self.signal_cleaning.emit(20)
                self.active_process_cleaning = 2

    def worker_HTL_cleaning(self):
        if self.active_process_cleaning == 2:
            t1 = self.read_temp_HTL()
            t2 = self.read_temp_HTL2()
            if t1 < 76 and t2 < 76:
                GPIO.output(self.grzalka_HTL, True)
            else:
                GPIO.output(self.grzalka_HTL, False)
                self.signal_cleaning.emit(40)
                self.active_process_cleaning = 3

    def getAdc_MASH_cleaning(self, channel):  # f. napelniania MASH
        if self.active_process_cleaning == 3:
        #check valid channel

            if ((channel>7)or(channel<0)):
                self.logger.error("Wrong channel on ADC")
                return

        # Preform SPI transaction and store returned bits in 'r'

            r = self.spi.xfer([1, (8+channel) << 4, 0])

        #Filter data bits from retruned bits

            adcOut = ((r[1] & 3) << 8) + r[2]
            percent = int(round(adcOut/10.24))

            if (percent <= 80):
                self.ui.checkBox_zHTL_OUT.setChecked(True)
                self.ui.checkBox_pompa_HTL_MASH.setChecked(True)
                self.ui.checkBox_zMASH_IN.setChecked(True)
                GPIO.output(self.zawor_HTL_OUT, True)
                GPIO.output(self.pompa_HTL_MASH, True)
                GPIO.output(self.zawor_MASH_IN, True)
            else:
                self.ui.checkBox_zHTL_OUT.setChecked(False)
                self.ui.checkBox_pompa_HTL_MASH.setChecked(False)
                self.ui.checkBox_zMASH_IN.setChecked(False)
                GPIO.output(self.zawor_HTL_OUT, False)
                GPIO.output(self.pompa_HTL_MASH, False)
                GPIO.output(self.zawor_MASH_IN, False)
                self.signal_cleaning.emit(60)
                self.active_process_cleaning = 4

    def getAdc_KETTLE_cleaning(self, channel):  # f. napelniania KETTLE
        if self.active_process_cleaning == 4:
        #check valid channel

            if ((channel>7)or(channel<0)):
                self.logger.error("Wrong channel on ADC")
                return

        # Preform SPI transaction and store returned bits in 'r'

            r = self.spi.xfer([1, (8+channel) << 4, 0])

        #Filter data bits from retruned bits

            adcOut = ((r[1] & 3) << 8) + r[2]
            percent = int(round(adcOut/10.24))

            if (percent < 80):  # opróżnienie
                self.ui.checkBox_zMASH_OUT.setChecked(True)
                self.ui.checkBox_pompa_HTL_MASH.setChecked(True)
                self.ui.checkBox_zKETTLE_IN.setChecked(True)
                GPIO.output(self.zawor_MASH_OUT, True)
                GPIO.output(self.pompa_HTL_MASH, True)
                GPIO.output(self.zawor_KETTLE_IN, True)

            else:
                self.ui.checkBox_zMASH_OUT.setChecked(False)
                self.ui.checkBox_pompa_HTL_MASH.setChecked(False)
                self.ui.checkBox_zKETTLE_IN.setChecked(False)
                GPIO.output(self.zawor_MASH_OUT, False)
                GPIO.output(self.pompa_HTL_MASH, False)
                GPIO.output(self.zawor_KETTLE_IN, False)
                self.signal_cleaning.emit(80)
                self.active_process_cleaning = 5


    def getAdc_KETTLE_out_cleaning(self, channel):  # f. oprozniania KETTLE
        if self.active_process_cleaning == 5:
            # check valid channel

            if ((channel > 7) or (channel < 0)):
                self.logger.error("Wrong channel on ADC")
                return

                # Preform SPI transaction and store returned bits in 'r'

            r = self.spi.xfer([1, (8 + channel) << 4, 0])

            # Filter data bits from retruned bits

            adcOut = ((r[1] & 3) << 8) + r[2]
            percent = int(round(adcOut / 10.24))

            if (percent > 0):  # oproznianie (dziala dopoki nie bedzie 0%)
                self.ui.checkBox_zH2O_COOLER.setChecked(True)
                self.ui.checkBox_zKLA_KETTLE_OUT.setChecked(True)
                GPIO.output(self.zawor_H2O_COOLER, True)
                GPIO.output(self.zawor_KETTLE_OUT, True)
            else:
                self.ui.checkBox_zH2O_COOLER.setChecked(False)
                self.ui.checkBox_zKLA_KETTLE_OUT.setChecked(False)
                GPIO.output(self.zawor_KETTLE_OUT, False)
                GPIO.output(self.zawor_H2O_COOLER, False)
                self.signal_cleaning.emit(100)
                self.active_process_cleaning = 6
                self.logger.info("End process cleaning [ok]")




if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ImageDialog()
    window.show()
    sys.exit(app.exec_())