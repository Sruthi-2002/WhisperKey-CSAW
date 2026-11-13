// tb_wave.v - focused waveform capture of the WhisperKey key-leak readback.
// Sends the secret trigger, then clocks 32 bits out over MISO (which carry the key).
// Dumps SCK / NORM_CS_N / MISO / BUSY to wave.vcd for rendering.
`timescale 1ns/1ps
module tb_wave;
    localparam [31:0] KEY=32'h8E043CB1, TRIGGER=32'h1337C0DE;
    reg SCK=0, RST_N, MOSI, NORM_CS_N, START, ENC_DEC;
    wire MISO, BUSY, ICE_LED;
    les_crypto_trojan #(.SECRET_KEY(KEY), .TRIGGER(TRIGGER)) dut(
        .SCK(SCK),.RST_N(RST_N),.MOSI(MOSI),.MISO(MISO),.NORM_CS_N(NORM_CS_N),
        .START(START),.ENC_DEC(ENC_DEC),.BUSY(BUSY),.ICE_LED(ICE_LED));
    task tick; begin #10 SCK=1; #10 SCK=0; end endtask
    integer i; reg [31:0] got;
    initial begin
        $dumpfile("wave.vcd"); $dumpvars(0, tb_wave);
        RST_N=1; MOSI=0; NORM_CS_N=1; START=0; ENC_DEC=0; tick;
        RST_N=0; tick; tick; RST_N=1; tick;
        // send the trigger word
        NORM_CS_N=0; for(i=31;i>=0;i=i-1) begin MOSI=TRIGGER[i]; tick; end NORM_CS_N=1; tick;
        START=1; tick; START=0; for(i=0;i<8;i=i+1) tick;   // run
        // readback: these 32 MISO bits are the leaked key
        NORM_CS_N=0; for(i=31;i>=0;i=i-1) begin got[i]=MISO; tick; end NORM_CS_N=1; tick;
        $display("readback over MISO = 0x%08X (key=0x%08X) %s", got, KEY, (got===KEY)?"LEAK":"-");
        $finish;
    end
endmodule
