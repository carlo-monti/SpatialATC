#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>

#define UDP_LISTEN_PORT 1234
#define AUDIO_RENDER_IP "127.0.0.1"
// 192.168.207.172
#define AUDIO_RENDER_PORT 4020

double map_range(double value) {
    if (value < -180.0 || value > 180.0) {
        fprintf(stderr, "Error: Input value must be between -180 and +180\n");
        //exit(EXIT_FAILURE);
    }
    return (value + 180.0) / 360.0;
}

int main() {
    int udp_sock, logger_sock;
    struct sockaddr_in recv_addr, send_addr;
    socklen_t addr_len = sizeof(struct sockaddr_in);
    char buffer[48];

    // Create UDP listener socket
    udp_sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (udp_sock < 0) {
        perror("UDP socket creation failed");
        //exit(EXIT_FAILURE);
    }

    memset(&recv_addr, 0, sizeof(recv_addr));
    recv_addr.sin_family = AF_INET;
    recv_addr.sin_port = htons(UDP_LISTEN_PORT);
    recv_addr.sin_addr.s_addr = inet_addr("127.0.0.1");

    if (bind(udp_sock, (struct sockaddr*)&recv_addr, sizeof(recv_addr)) < 0) {
        perror("Bind failed");
        close(udp_sock);
        exit(EXIT_FAILURE);
    }

    // Create logger socket
    logger_sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (logger_sock < 0) {
        perror("Logger socket creation failed");
        close(udp_sock);
        exit(EXIT_FAILURE);
    }

    memset(&send_addr, 0, sizeof(send_addr));
    send_addr.sin_family = AF_INET;
    send_addr.sin_port = htons(AUDIO_RENDER_PORT);
    send_addr.sin_addr.s_addr = inet_addr(AUDIO_RENDER_IP);
    
    fprintf(stderr, "Head Tracker UDP Mapper is forwarding from port %d to %s:%d", UDP_LISTEN_PORT, AUDIO_RENDER_IP, AUDIO_RENDER_PORT);

    double previous_y = 0;

    while (1) {
        ssize_t received = recvfrom(udp_sock, buffer, sizeof(buffer), 0,
                                    (struct sockaddr*)&recv_addr, &addr_len);
        if (received != 48) {
            fprintf(stderr, "Invalid packet size: %zd bytes\n", received);
            continue;
        }
        double y, p, r;
        memcpy(&y, buffer + 3 * sizeof(double), sizeof(double));
        memcpy(&p, buffer + 4 * sizeof(double), sizeof(double));
        memcpy(&r, buffer + 5 * sizeof(double), sizeof(double));

        if(1){

            // opentrack keep sending the last value even if the tracking is lost
            // so we need to avoid this behaviour and we
            // send value only if is different from the previous one 
            // it is a float with 5 decimals (it is definitely different every time)

            double my = map_range(y);
            double mp = map_range(p);
            double mr = map_range(r);

            char msg[100];
            snprintf(msg, sizeof(msg), "%f %f %f;", my, mp, mr);

            sendto(logger_sock, msg, strlen(msg), 0, (struct sockaddr*)&send_addr, sizeof(send_addr));
        }
        
    }

    close(udp_sock);
    close(logger_sock);
    return 0;
}
