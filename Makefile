# WhisperKey - one-command build/verify of the whole attack.
RTL=rtl
TB=tb
IV=iverilog -g2012

.PHONY: all verify vector exploit insert ast area wave console clean

all: verify
	@echo "== WhisperKey: all checks passed =="

# regenerate the Trojan (text pipeline) and run stealth + exploit checks
verify:
	python3 tools/pipeline.py

# validate the recovered cipher against the known challenge test vector
vector:
	$(IV) -o $(RTL)/sim_vec $(RTL)/les_crypto_golden.v $(TB)/tb_golden_vector.v
	cd $(RTL) && vvp sim_vec && rm -f sim_vec

# run only the exploit/stealth testbench
exploit:
	$(IV) -o $(RTL)/sim_exp $(RTL)/les_crypto_golden.v $(RTL)/les_crypto_trojan.v $(TB)/tb_exploit.v
	cd $(RTL) && vvp sim_exp && rm -f sim_exp *.vcd

# alternative insertion: AST-level transform (pyverilog)
ast:
	python3 tools/ast_insert.py

# synthesized area overhead (Yosys)
area:
	python3 tools/area_report.py

# render the key-leak waveform (PNG in reports/)
wave:
	python3 tools/render_waveform.py

# interactive attacker console
console:
	python3 tools/attack_console.py

clean:
	rm -f $(RTL)/sim_* $(RTL)/*.vcd
