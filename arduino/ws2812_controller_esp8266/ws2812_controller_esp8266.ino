#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <WiFiUdp.h>
#include <NeoPixelBrightnessBus.h>

// Set to the number of LEDs in your LED strip
#define NUM_LEDS 120
// Maximum power draw, in mA - assume at least 250 for the microcontroller outside of the LED draw
#define POWER_BUDGET 3500
// Maximum number of packets to hold in the buffer. Don't change this.
#define BUFFER_LEN 1024
// Toggles FPS output (1 = print FPS over serial, 0 = disable output)
#define PRINT_FPS 1

//NeoPixelBus settings
const uint8_t PixelPin = 3;  // make sure to set this to the correct pin, ignored for Esp8266(set to 3 by default for DMA)

// Wifi and socket settings
const char* ssid     = "CarpetShark";
const char* password = "SaK2Kutuq2Be6w";
unsigned int localPort = 7777;
char packetBuffer[BUFFER_LEN];

// LED strip
NeoPixelBrightnessBus<NeoGrbFeature, Neo800KbpsMethod> ledstrip(NUM_LEDS, PixelPin);

WiFiUDP port;

// Network information
// IP must match the IP in config.py
IPAddress ip(10, 0, 1, 10);
// Set gateway to your router's gateway
IPAddress gateway(10, 0, 0, 1);
IPAddress subnet(255, 255, 255, 0);

uint8_t ledpower[NUM_LEDS];
int ledpower_samples[100], ledpower_sample_count = 0;

void setup() {
    Serial.begin(115200);

    WiFi.config(ip, gateway, subnet);
    WiFi.begin(ssid, password);
    Serial.println("");
    // Connect to wifi and print the IP address over serial
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("");
    Serial.print("Connected to ");
    Serial.println(ssid);
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
    port.begin(localPort);

    // LED test
    ledstrip.Begin();//Begin output
    ledtest();
    // ledstrip.Show();//Clear the strip for use

    for (int i = 0; i < NUM_LEDS; i++) {
      ledpower[i] = 0;
    }
    for (int i = 0; i < 100; i++) {
      ledpower_samples[i] = 0;
    }
}

void ledtest() {
  RgbColor c[4];
  c[0] = RgbColor(255, 0, 0);
  c[1] = RgbColor(0, 255, 0);
  c[2] = RgbColor(0, 0, 255);
  c[3] = RgbColor(0, 0, 0);
  for (int i = 0; i < 4; i++) {
    for (int n = 0; n < NUM_LEDS; n++) {
      ledstrip.SetPixelColor(n, c[i]);
      ledstrip.Show();
      delay(10);
    }
  }
}

uint8_t N = 0;
#if PRINT_FPS
    uint16_t fpsCounter = 0;
    uint32_t secondTimer = 0;
#endif

void loop() {
    // Read data over socket
    int packetSize = port.parsePacket();
    // If packets have been received, interpret the command
    if (packetSize) {
        int len = port.read(packetBuffer, BUFFER_LEN);
        for(int i = 0; i < len; i+=4) {
            packetBuffer[len] = 0;
            N = packetBuffer[i];
            RgbColor pixel((uint8_t)packetBuffer[i+1], (uint8_t)packetBuffer[i+2], (uint8_t)packetBuffer[i+3]);
            ledstrip.SetPixelColor(N, pixel);

            ledpower[N] = (((float) packetBuffer[i+1] / 255.0) * 20) + (((float) packetBuffer[i+2] / 255.0) * 20) + (((float) packetBuffer[i+3] / 255.0) * 20);
        }
        for (int i = 0; i < NUM_LEDS; i++) {
          ledpower_samples[ledpower_sample_count] += ledpower[i];
        }
        int bri = ((float) POWER_BUDGET / (float) ledpower_samples[ledpower_sample_count]) * 255;
        if (bri > 255) bri = 255;
        ledstrip.SetBrightness((uint8_t) bri);
        ledpower_sample_count++;
        ledstrip.Show();
        #if PRINT_FPS
            fpsCounter++;
//            Serial.print("/");//Monitors connection(shows jumps/jitters in packets)
        #endif
    }
    #if PRINT_FPS
        if (millis() - secondTimer >= 1000U) {
            secondTimer = millis();
            int power = 0;
            for (int i = 0; i < ledpower_sample_count; i++) {
              if (ledpower_samples[i] > power) power = ledpower_samples[i];
              ledpower_samples[i] = 0;
            }
            ledpower_sample_count = 0;
            Serial.printf("FPS: %d, power: %d\n", fpsCounter, power);
            fpsCounter = 0;
        }   
    #endif
}
