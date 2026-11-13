// Validate the recovered golden design against the known challenge test vector.
`timescale 1ns/1ps
module tb_golden_vector;
    reg SCK=0, RST_N, MOSI, NORM_CS_N, START, ENC_DEC;
    wire MISO, BUSY, ICE_LED;
    les_crypto_golden dut(.SCK(SCK),.RST_N(RST_N),.MOSI(MOSI),.MISO(MISO),
        .NORM_CS_N(NORM_CS_N),.START(START),.ENC_DEC(ENC_DEC),.BUSY(BUSY),.ICE_LED(ICE_LED));

    task tick; begin #10 SCK=1; #10 SCK=0; end endtask
    task spi_write(input [31:0] d); integer i; begin
        NORM_CS_N=0; for(i=31;i>=0;i=i-1) begin MOSI=d[i]; tick; end NORM_CS_N=1; tick; end endtask
    task spi_read(output [31:0] d); integer i; begin
        NORM_CS_N=0; for(i=31;i>=0;i=i-1) begin d[i]=MISO; tick; end NORM_CS_N=1; tick; end endtask
    task run_op(input [31:0] w, input mode, output [31:0] r); integer c; begin
        spi_write(w); ENC_DEC=mode; START=1; tick; START=0;
        for(c=0;c<8;c=c+1) tick; spi_read(r); end endtask

    reg [31:0] ct, pt;
    initial begin
        RST_N=1; MOSI=0; NORM_CS_N=1; START=0; ENC_DEC=0; tick;
        RST_N=0; tick; tick; RST_N=1; tick;
        run_op(32'h59C359C3, 1'b0, ct);
        $display("ENCRYPT 0x59C359C3 -> 0x%08X (expect 0x9CD84392) : %s", ct, (ct===32'h9CD84392)?"PASS":"FAIL");
        RST_N=0; tick; tick; RST_N=1; tick;
        run_op(32'h9CD84392, 1'b1, pt);
        $display("DECRYPT 0x9CD84392 -> 0x%08X (expect 0x59C359C3) : %s", pt, (pt===32'h59C359C3)?"PASS":"FAIL");
        $finish;
    end
endmodule
