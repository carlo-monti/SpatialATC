#define BUTTON_PTT_PIN 12
#define BUTTON_PHONE_PIN 27
#define TRANSMISSION_PERIOD 80
#include <Bounce2.h>

long last_transmission_ptt = 0;
long last_transmission_phone = 0;

Bounce2::Button button_ptt = Bounce2::Button();
Bounce2::Button button_phone = Bounce2::Button();

void setup() {
  Serial.begin(9600);
  
  button_ptt.attach( BUTTON_PTT_PIN, INPUT_PULLUP);
  button_ptt.interval(10); 
  button_ptt.setPressedState(0); 

  button_phone.attach( BUTTON_PHONE_PIN, INPUT_PULLUP);
  button_phone.interval(10); 
  button_phone.setPressedState(0); 
}

void loop() {
  button_ptt.update();
  button_phone.update();
  
  if (button_ptt.rose()) {  // Detects button press (HIGH to LOW transition)
    Serial.println(0);
  }
  if (button_phone.rose()) {  // Detects button press (HIGH to LOW transition)
    Serial.println(1);
  }

  if(millis() > last_transmission_ptt + TRANSMISSION_PERIOD && (button_ptt.read() == 0)){
    Serial.println(0);
    last_transmission_ptt = millis();
  }
  if(millis() > last_transmission_phone + TRANSMISSION_PERIOD && (button_phone.read() == 0)){
    Serial.println(1);
    last_transmission_phone = millis();
  }
}
