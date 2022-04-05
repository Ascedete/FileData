from filedata.filedata import FileData

txt = """/////////////////////////////////////////////////////////////////////////////////////////////////
// Testcase file: this file contains the stimuli/story of what needs to be simulated
//
// Following defines are available if full CMD-line approach is used:
//       `BENCH: name of the simulation bench used
//       `TC: name of the testcase
//       `TC_CONF: name of the testcase configuration
//       `RUN: name of the run
//
//       `AMS_RESULTS_DIR: directory where simulation results are stored (/localrundirs/<user>/<project>/<rev>/BENCH/RUN/TC/TC_CONF/)
//       `TESTCASE_DIR: testcase directory  (/mixed/simulations/BENCH/TC)
//       `SETUP_DIR: setup directory (/mixed/simulations/BENCH/setup)
//       `DUT_DIR: dut directory (/mixed/simulations/BENCH/dut)
//       `ENVIRONMENT_DIR: environment directory  (/mixed/simulations/BENCH/environment)
//       `OUTPUT_DIR: output log directory (/mixed/simulations/BENCH/TC/output__RUN__TC_CONF)
//       `NETLIST_DIR: netlist directory (/analog/release</sandbox>/LIB/CELL/VIEW)
//
//
/////////////////////////////////////////////////////////////////////////////////////////////////
//
//  Description: Example ASM program execution
//
//  1) Software generates a staircase output on IO's
//  2) Software turns on PWM on IO's
//
//  $Author: pts $
//  $Revision: 1.4 $
//  $Date: Tue Jun 15 10:49:09 2021 $
//  $Source: /mnt/dss/syncdata/dss.colo.elex.be/3411/server_vault/Projects/m81346/vBA/mixed/simulations/top/tc_cp/tc_vams.inc.rca $
//
/////////////////////////////////////////////////////////////////////////////////////////////////
//
// 2018/11/27 svj - initial version
`ifndef TC `define TC "dummy4compile" `endif

`ifndef CP_TR `define CP_TR 500e-6 `endif
`ifndef VLOAD `define VLOAD 12	`endif
reg en_cp_fets_load; 	initial en_cp_fets_load = 1'b0;
reg en_cp_pdrv_load; 	initial en_cp_pdrv_load = 1'b0;

parameter real ILOAD_FETs_CP		= 4.8e-3	`ifndef HL_MODEL from (0:inf) `endif;		// [A] external predriver FETs
//parameter real ILOAD_FETs_CP		= 100e-3	`ifndef HL_MODEL from (0:inf) `endif;		// [A] external predriver FETs
parameter real ILOAD_pDRV_CP		= 1.2e-3	`ifndef HL_MODEL from (0:inf) `endif;		// [A] external predriver circuitry
parameter real LOAD_VOLTAGE = `VLOAD; // legacy value from older versions

real trigger_val_uv, trigger_val_ov;

real RLOAD_FETs_CP;
real RLOAD_pDRV_CP;

initial RLOAD_FETs_CP = (LOAD_VOLTAGE+4.6)/ILOAD_FETs_CP;
initial RLOAD_pDRV_CP = (LOAD_VOLTAGE+4.6)/ILOAD_pDRV_CP;

initial trigger_val_uv = 0; 
initial trigger_val_ov = 0;

parameter CSTORE_CAP	 = 3e-6; // Storage Capacity Value of Chargepump 
parameter CFLY_CAP		 = 600e-9; // Flycap Capacity Value of Chargepump

`ifdef OLD_CAPS
	   defparam CSTORE_CAP = 1e-6;
	   defparam CFLY_CAP = 100e-9;
`endif

defparam auto_stop_after  = 15*ms;
defparam printSimTimeStep = 0.1*ms;

integer stairs_done=0;
integer count_pwm_edges=0;

// suppress undriven Z
wire #(5*us,100) api_started = `TOP_DIG_PATH.mupet.sync_in_application;
//wire #(5*us,100) api_started = `TOP_DIG_PATH.mupet.mupet_activation.in_application;
wire               ov_vboost = /*`TOP_DIG_PATH.ms_ov_boost | */`TOP_DIG_PATH.ms_ov_boosti; // taken out: delays the
wire               uv_vboost = /*`TOP_DIG_PATH.ms_uv_boost | */`TOP_DIG_PATH.ms_uv_boosti; //   measurement triggers
wire  cpdrv_dig  = cmph[`A_CPDRV];
wire  vboost_dig = cmph[`A_VBOOST];

parameter real	  vs_val		= 12
		, vlin_val		= vs_val
		, v_vdda_min		= 3.1		// defaults for 3V operation
		, v_vdda_max		= 3.6
		, v_vdda5_min		= 4.9		// defaults for 5V operation
		, v_vdda5_max		= 5.1

// spec for VCPDRV
		, v_cpdrv_min10V 	= 7.0,	v_cpdrv_max10V  = vs_val+0.1	// VSM > 10V
		, v_cpdrv_min8V	  	= 5.5,	v_cpdrv_max8V   = vs_val+0.1	// 8V < VSM < 10V
		, v_cpdrv_minlt8V 	= 3.0,	v_cpdrv_maxlt8V = vs_val+0.1	// VSM < 8V

// spec declarion OV,UV -> add V(VSM) before use
		, v_boost_min10V 	= 7.0,	v_boost_max10V  = 9.5	// VSM > 10V
		, v_boost_min8V	  	= 5.5,	v_boost_max8V   = 9.5	// 8V < VSM < 10V
		, v_boost_minlt8V 	= 3.0,	v_boost_maxlt8V = 8.0	// VSM < 8V
		, v_boost_ov_min  	= 9.5,	v_boost_ov_max  = 10.5	// overvolt
		, v_boost_uv_min  	= 6.3,	v_boost_uv_max  = 6.6	// undervolt
		, v_uvov_hyst_min	= 0.200,v_uvov_hyst_max	= 0.4+0.05 // hysteresis OV, UV comps
;
real		  i_vdda		= 0	// store measurements
		, i_vdda_pre_mrb		= 0
		, i_vddd		= 0
		, ibias			= 0	// measure OVUV bias (or others)
		, v_vboost		= 0
		, v_vsm			= 0
		, v_cpdrv		= 0

		, limit_vcpdrv_min 	= v_cpdrv_min10V  
		, limit_vcpdrv_max 	= v_cpdrv_max10V  

		// must add v(VSM) to all values 
		, limit_vboost_min 	= v_boost_min10V // +v_vsm  //  // initial with vsm=0.0V
		, limit_vboost_max 	= v_boost_max10V // +v_vsm  //   
		, limit_uv_min		= v_boost_uv_min // +v_vsm  // 
		, limit_uv_max		= v_boost_uv_max // +v_vsm  // 
		, limit_ov_min		= v_boost_ov_min // +v_vsm  // 
		, limit_ov_max		= v_boost_ov_max // +v_vsm  // 
		;

// Charge Pump application circuitry
`ifndef HL_MODEL
BAV99 DVFLYUPR (PIN_VSM,VFLY);
BAV99 DVFLYLWR (VFLY,PIN_VBOOST);
capacitor #(.c(CSTORE_CAP)) C_STORE (PIN_VBOOST, PIN_VSM);
capacitor #(.c(CFLY_CAP)) C_FLY (VFLY, PIN_CPDRV);

analog begin
  I(PIN_VBOOST,PIN_VSM) <+ transition(V(PIN_VBOOST,PIN_VSM)*en_cp_fets_load*1/RLOAD_FETs_CP,0,1u);
  I(PIN_VBOOST,PIN_VSM) <+ transition(V(PIN_VBOOST,PIN_VSM)*en_cp_pdrv_load*1/RLOAD_pDRV_CP,0,1u);
end

//`else
//initial #0 no_meas_errors = 1; // disable analog measurement fails, default by HL_MODEL now
`endif
`ifndef VSM_VOLTAGE
	`define VSM_VOLTAGE 48
`endif
`include "../environment/helpers.vams"
initial #0 begin:main_sequence
	IF.reset;
	#1
	ramp_vs_vsm(12, `VSM_VOLTAGE, 10e-6);

	#100 wait(MRB === 1); sim_msg = "RESET DONE";
	$display("%0s================================================================%0s", blue, normal);
	$display("%0s***** %0s / %0s (sdf: %0s) *****%0s", blue,`TC, `TC_CONF, del_case,normal);
	$display("%0s================================================================%0s", blue, normal);
	$display("%0s Simulation %0s driver charge pump behavior%0s", blue, dev_name, normal);
	$display("%0s\t- controlled by Flash program%0s", blue, normal);
	$display("%0s INFO\tVS\t%.1fV (from %m, at start)%0s",blue,vs_val,normal);
	$display("%0s INFO\t%0sTemp\t%.0fC %0s%0s(from amsControlSpectre.scs)%0s",blue,bold,$temperature-273.15,normal,blue,normal);
	$display("%0s================================================================%0s", blue, normal);

    `ifndef HL_MODEL
        i_vdda_pre_mrb = 1e6*($cds_get_analog_value("top.CHIP.AA_DIE.SUSY_SHELL.AA_ANALOG.A_SUPPLY_SYSTEM_CORE.A_REG_V3V3.V3V3" ,"flow") ); // scale to uA as limit
    `endif
	@(posedge api_started) sim_msg = "IN_APPLICATION";
	en_cp_pdrv_load = 1;
	IF.rd( `A_VSM, GET_VOUT, v_vsm);
	`ifndef SV_MODEL
	i_vdda = 1e12*($cds_get_analog_value("top.CHIP.AA_DIE.SUSY_SHELL.AA_ANALOG.A_SUPPLY_SYSTEM_CORE.A_REG_V3V3.V3V3" ,"flow") ); 
	
	measAnalog("V_VBGA", $cds_get_analog_value("top.CHIP.AA_DIE.SUSY_SHELL.AA_ANALOG.A_SUPPLY_SYSTEM_CORE.VBG_A", "potential"), 1.16, 1.22, 1.0, "V"); 
	measAnalog("V_VBGD", $cds_get_analog_value("top.CHIP.AA_DIE.SUSY_SHELL.AA_ANALOG.A_SUPPLY_SYSTEM_CORE.VBG_D", "potential"), 1.16, 1.22, 1.0, "V"); 
	`endif
   // check 5V option limits, compared to current measurement from 3V it should not increase too much
	`ifndef SV_MODEL
	measAnalog("I_VDDA", abs(i_vdda), abs(i_vdda_pre_mrb)*0.5, abs(i_vdda_pre_mrb)*1.9, 1e-6, "uA");
	measAnalog("V_VDDA", V(PIN_VDDA), v_vdda_min, v_vdda_max, 1.0, "V"); // limits set by used TC mode
	`endif
	wait(`TOP_DIG_PATH.ms_en_cp);
	$display("\tCharge pump is enabled now");

	wait(!`TOP_DIG_PATH.ms_uv_boost);
	en_cp_fets_load = 1;

	#(300*us);
	`ifndef SV_MODEL 
		IF.rd(`A_VSM, GET_VOUT, v_vsm);
		IF.rd(`A_VBOOST, GET_VOUT, v_vboost);
		case (1) 
			(v_vsm > 10):				 measAnalog("MLX81346-218_VBOOST_HI", v_vboost-v_vsm, 7.5, 10, 1, "V");
			(v_vsm > 8 && v_vsm < 10): measAnalog("MLX81346-219_VBOOST_NOM", v_vboost-v_vsm, 5.5, 9.5, 1, "V");
			(v_vsm < 8): 				 measAnalog("MLX81346-220_VBOOST_NOM", v_vboost-v_vsm, 3.5, 8, 1, "V");
		endcase
	`endif

	

	wait(!`TOP_DIG_PATH.ms_en_cp);
	`ifdef HL_MODEL
	$display("\t%m stops sim for digital model (remaining stimuli are analog function, focus to charging)");
	end_simulation(errors);
     `endif
	 // en_cp_fets_load = 0;
	trigger_val_uv = 0; // Hysteresis faulty, because of high VBOOST slew rate
	wait(`TOP_DIG_PATH.ms_en_cp);
	$display("\twait for charge pump got disabled (to drive from Pin)");
	wait(!`TOP_DIG_PATH.ms_en_cp);
	en_cp_fets_load = 0;
	en_cp_pdrv_load = 0;

	#(100*us);    
	IF.wr(`A_VBOOST, SET_TR, 0.1e-6);
	IF.rd(`A_VBOOST, GET_VOUT, v_vboost);	
	IF.wr(`A_VBOOST, SET_VOUT, v_vboost);	
	IF.wr(`A_VBOOST, SET_SW, CLOSE);
	
	IF.rd(`A_VSM, GET_VOUT, v_vsm);
	IF.wr(`A_VBOOST, SET_TR, `CP_TR/2);
	IF.wr(`A_VBOOST, SET_VOUT, v_vsm + 12);	// ramp up to ov - question, why moe took very high voltage

	$display("\tOverdrive VBOOST to 23V/500us ramp, wait for OV");

	@(posedge ov_vboost) #(20*us) 
	IF.wr(`A_VBOOST, SET_TR, `CP_TR);
	IF.wr(`A_VBOOST, SET_VOUT, v_vsm);

	$display("\tPulldown VBOOST to 5V/500us ramp, wait for UV");
	@ (posedge uv_vboost) IF.wr(`A_VBOOST, SET_SW, OPEN);
	#(1*ms) end_simulation(errors);

end

//////////////////////////////   MEASUREMENTS   //////////////////////////////

always@(`TOP_DIG_PATH.ms_tr_cp[3:0])
	case(`TOP_DIG_PATH.ms_tr_cp[3:0])
	4'h0: begin RLOAD_FETs_CP = (8)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (LOAD_VOLTAGE+8)/     ILOAD_pDRV_CP; end
	4'h1: begin RLOAD_FETs_CP = (8.5)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (8.5)/   ILOAD_pDRV_CP; end
	4'h2: begin RLOAD_FETs_CP = (9)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (9)/     ILOAD_pDRV_CP; end
	4'h3: begin RLOAD_FETs_CP = (9.4)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (9.4)/   ILOAD_pDRV_CP; end
	4'h4: begin RLOAD_FETs_CP = (9.9)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (9.9)/   ILOAD_pDRV_CP; end
	4'h5: begin RLOAD_FETs_CP = (10.3)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (10.3)/  ILOAD_pDRV_CP; end
	4'h6: begin RLOAD_FETs_CP = (10.7)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (10.7)/  ILOAD_pDRV_CP; end
	4'h7: begin RLOAD_FETs_CP = (11.2)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (11.2)/  ILOAD_pDRV_CP; end
	4'h8: begin RLOAD_FETs_CP = (4.6)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (4.6)/   ILOAD_pDRV_CP; end
	4'h9: begin RLOAD_FETs_CP = (5)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (5)/     ILOAD_pDRV_CP; end
	4'hA: begin RLOAD_FETs_CP = (5.4)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (5.4)/   ILOAD_pDRV_CP; end
	4'hB: begin RLOAD_FETs_CP = (5.9)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (5.9)/   ILOAD_pDRV_CP; end
	4'hC: begin RLOAD_FETs_CP = (6.3)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (6.3)/   ILOAD_pDRV_CP; end
	4'hD: begin RLOAD_FETs_CP = (6.8)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (6.8)/   ILOAD_pDRV_CP; end
	4'hE: begin RLOAD_FETs_CP = (7.2)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (7.2)/   ILOAD_pDRV_CP; end
	4'hF: begin RLOAD_FETs_CP = (7.7)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (7.7)/   ILOAD_pDRV_CP; end
	default: begin RLOAD_FETs_CP = (4.6)/ILOAD_FETs_CP;	RLOAD_pDRV_CP = (4.6)/   ILOAD_pDRV_CP; end
	endcase

always @(`TOP_DIG_PATH.ms_tr_cp[3:0]) if (api_started===1) #(200*us) 
	begin
	IF.rd(`A_VSM, GET_VOUT, v_vsm);
	@(posedge vboost_dig) #(us);
	IF.rd(`A_VBOOST, GET_VOUT, v_vboost);
	`ifndef SV_MODEL
	@(posedge cpdrv_dig) #(us) IF.rd(`A_CPDRV, GET_VOUT, v_cpdrv);
	#0 measAnalog("V_VBOOST", v_vboost, limit_vboost_min, limit_vboost_max, 1.0, "V"); 
	#0 measAnalog("V_CPDRV",  v_cpdrv,  limit_vcpdrv_min, limit_vcpdrv_max, 1.0, "V"); 
	`endif
	end								

//////////////////////////////   MESSAGES   //////////////////////////////
always @(v_vsm) // triggered by measurement update
	if      (v_vsm > 10)	begin
				limit_vboost_min=v_boost_min10V+v_vsm; limit_vcpdrv_min=v_cpdrv_min10V;
				limit_vboost_max=v_boost_max10V+v_vsm; limit_vcpdrv_max=v_cpdrv_max10V;
				end
	else if (v_vsm > 8) 	begin
				limit_vboost_min=v_boost_min8V+v_vsm; limit_vcpdrv_min=v_cpdrv_min8V;
				limit_vboost_max=v_boost_max8V+v_vsm; limit_vcpdrv_max=v_cpdrv_max8V;
				end
	else /* vsm < 8V */	begin
				limit_vboost_min=v_boost_minlt8V+v_vsm; limit_vcpdrv_min=v_cpdrv_minlt8V;
				limit_vboost_max=v_boost_maxlt8V+v_vsm; limit_vcpdrv_max=v_cpdrv_maxlt8V;
				end
/*
		, v_boost_min10V 	= 7.0,	v_boost_max10V  = 9.5	// VSM > 10V
		, v_boost_min8V	  	= 5.5,	v_boost_max8V   = 9.5	// 8V < VSM < 10V
		, v_boost_minlt8V 	= 3.0,	v_boost_maxlt8V = 8.0	// VSM < 8V
		, v_boost_ov_min  	= 9.5,	v_boost_ov_max  = 10.5	// overvolt
		, v_boost_uv_min  	= 6.3,	v_boost_uv_max  = 6.5	// undervolt
		, v_uvov_hyst_min	= 0.2,	v_uvov_hyst_max	= 0.3 

*/

always @(ov_vboost) if (api_started===1) #5 begin // let it settle
	IF.rd(`A_VSM,    GET_VOUT, v_vsm);
	IF.rd(`A_VBOOST, GET_VOUT, v_vboost);
	IF.rd(`A_CPDRV,  GET_VOUT, v_cpdrv);
	limit_uv_min=v_boost_uv_min+v_vsm;	limit_uv_max=v_boost_uv_max+v_vsm;
	limit_ov_min=v_boost_ov_min+v_vsm;	limit_ov_max=v_boost_ov_max+v_vsm;
`ifndef HL_MODEL
        ibias = 1e6*abs($cds_get_analog_value("top.CHIP.AA_DIE.CP_SHELL.OVUV_VBOOST_I.IPD1U" ,"flow") ); 
`else	ibias=1; `endif
	#0 measAnalog("ibias_1u_pd(OV,UV)", ibias, 0.7, 1.5, 1.0, "uA"); // log only
  	if (ov_vboost) begin
		$display("\t%0sOV(VBOOST) triggered at %.3fV%0s",bold,v_vboost,normal);
		// measAnalog("V(VSM)", v_vsm, 3, 20, 1.0, "V"); // log only
		measAnalog("OV_VBOOST_LH", v_vboost, limit_ov_min, limit_ov_max, 1.0, "V");
    `ifndef SV_MODEL
		if (trigger_val_ov != 0) begin
			measAnalog("VBOOST_OV_HYST", abs(v_vboost - trigger_val_ov), v_uvov_hyst_min, v_uvov_hyst_max, 1.0, "V");
		end
    `endif
		  trigger_val_ov = v_vboost;
		end
		else begin
      $display("\t%0sOV(VBOOST) released at %.3fV%0s",bold,v_vboost,normal);
    // measAnalog("V(VSM)", v_vsm, 3, 20, 1.0, "V"); // log only
      measAnalog("OV_VBOOST_HL", v_vboost, limit_ov_min, limit_ov_max, 1.0, "V");
      `ifndef SV_MODEL
      if (trigger_val_ov != 0) begin
        measAnalog("VBOOST_OV_HYST", abs(v_vboost - trigger_val_ov), v_uvov_hyst_min, v_uvov_hyst_max, 1.0, "V");
      end
      `endif
      trigger_val_ov = v_vboost;
		end
	end
always @(uv_vboost) if (api_started===1) #5 begin // let it settle
	IF.rd(`A_VSM,    GET_VOUT, v_vsm);
	IF.rd(`A_VBOOST, GET_VOUT, v_vboost);
	IF.rd(`A_CPDRV,  GET_VOUT, v_cpdrv);
	limit_uv_min=v_boost_uv_min+v_vsm-v_uvov_hyst_max;	limit_uv_max=v_boost_uv_max+v_vsm+v_uvov_hyst_max;
	limit_ov_min=v_boost_ov_min+v_vsm-v_uvov_hyst_max;	limit_ov_max=v_boost_ov_max+v_vsm+v_uvov_hyst_max;
`ifndef HL_MODEL
        ibias = 1e6*abs($cds_get_analog_value("top.CHIP.AA_DIE.CP_SHELL.OVUV_VBOOST_I.IPD1U" ,"flow") ); 
`else	ibias=1; `endif
	#0 measAnalog("ibias_1u_pd(OV,UV)", ibias, 0.7, 1.5, 1.0, "uA"); // log only
	
	if (uv_vboost) begin
		$display("\t%0sUV(VBOOST) triggered at %.3fV%0s",bold,v_vboost,normal);
		// measAnalog("V(VSM)", v_vsm, 3, 20, 1.0, "V"); // log only
		measAnalog("UV_VBOOST_LH", v_vboost, limit_uv_min, limit_uv_max, 1.0, "V");
    `ifndef SV_MODEL
		if (trigger_val_uv != 0) begin
			measAnalog("VBOOST_UV_HYST", abs(v_vboost - trigger_val_uv), v_uvov_hyst_min, v_uvov_hyst_max, 1.0, "V");
		end
    `endif
		trigger_val_uv = v_vboost;
		end
		else begin
		$display("\t%0sUV(VBOOST) released at %.3fV%0s",bold,v_vboost,normal);
		// measAnalog("V(VSM)", v_vsm, 3, 20, 1.0, "V"); // log only
		measAnalog("UV_VBOOST_HL", v_vboost, limit_uv_min, limit_uv_max, 1.0, "V"); //slightly above, but release is not critical
    `ifndef SV_MODEL
		if (trigger_val_uv != 0) begin
			measAnalog("VBOOST_UV_HYST", abs(v_vboost - trigger_val_uv), v_uvov_hyst_min, v_uvov_hyst_max, 1.0, "V");
		end
    `endif
		trigger_val_uv = v_vboost;
		end
	end

always @(posedge `TOP_DIG_PATH.ms_switch_vdda_to_5v)
      $display("\n\t%0sVDDA 5V option gets activated (by asm)%0s",bold,normal);
      
always @(IO) if (MRB & api_started)
      #5 $display("*** INFO *** @%t %m: IO[11:0] = %04b_%04b_%04b", $time, IO[11:8], IO[7:4], IO[3:0]);

initial #50 if (`TC == "tc_cp") set_term_title("Driver charge pump ");
           else                 set_term_title("Driver charge pump VDDA=5V");
// vi:syntax=verilogams

/////////////////////////////////////////////////////////////////////////////////////////////////
// Testcase file: this file contains the stimuli/story of what needs to be simulated
//
// Following defines are available if full CMD-line approach is used:
//       `BENCH: name of the simulation bench used
//       `TC: name of the testcase
//       `TC_CONF: name of the testcase configuration
//       `RUN: name of the run
//
//       `AMS_RESULTS_DIR: directory where simulation results are stored (/localrundirs/<user>/<project>/<rev>/BENCH/RUN/TC/TC_CONF/)
//       `TESTCASE_DIR: testcase directory  (/mixed/simulations/BENCH/TC)
//       `SETUP_DIR: setup directory (/mixed/simulations/BENCH/setup)
//       `DUT_DIR: dut directory (/mixed/simulations/BENCH/dut)
//       `ENVIRONMENT_DIR: environment directory  (/mixed/simulations/BENCH/environment)
//       `OUTPUT_DIR: output log directory (/mixed/simulations/BENCH/TC/output__RUN__TC_CONF)
//       `NETLIST_DIR: netlist directory (/analog/release</sandbox>/LIB/CELL/VIEW)
//
//
/////////////////////////////////////////////////////////////////////////////////////////////////
//
//  Description: Example ASM program execution
//
//  1) Software generates a staircase output on IO's
//  2) Software turns on PWM on IO's
//
//  $Author: pts $
//  $Revision: 1.4 $
//  $Date: Tue Jun 15 10:49:09 2021 $
//  $Source: /mnt/dss/syncdata/dss.colo.elex.be/3411/server_vault/Projects/m81346/vBA/mixed/simulations/top/tc_cp/tc_vams.inc.rca $
//
/////////////////////////////////////////////////////////////////////////////////////////////////
//
// 2018/11/27 svj - initial version
`ifndef TC `define TC "dummy4compile" `endif

`ifndef CP_TR `define CP_TR 500e-6 `endif
`ifndef VLOAD `define VLOAD 12	`endif
reg en_cp_fets_load; 	initial en_cp_fets_load = 1'b0;
reg en_cp_pdrv_load; 	initial en_cp_pdrv_load = 1'b0;

parameter real ILOAD_FETs_CP		= 4.8e-3	`ifndef HL_MODEL from (0:inf) `endif;		// [A] external predriver FETs
//parameter real ILOAD_FETs_CP		= 100e-3	`ifndef HL_MODEL from (0:inf) `endif;		// [A] external predriver FETs
parameter real ILOAD_pDRV_CP		= 1.2e-3	`ifndef HL_MODEL from (0:inf) `endif;		// [A] external predriver circuitry
parameter real LOAD_VOLTAGE = `VLOAD; // legacy value from older versions

real trigger_val_uv, trigger_val_ov;

real RLOAD_FETs_CP;
real RLOAD_pDRV_CP;

initial RLOAD_FETs_CP = (LOAD_VOLTAGE+4.6)/ILOAD_FETs_CP;
initial RLOAD_pDRV_CP = (LOAD_VOLTAGE+4.6)/ILOAD_pDRV_CP;

initial trigger_val_uv = 0; 
initial trigger_val_ov = 0;

parameter CSTORE_CAP	 = 3e-6; // Storage Capacity Value of Chargepump 
parameter CFLY_CAP		 = 600e-9; // Flycap Capacity Value of Chargepump

`ifdef OLD_CAPS
	   defparam CSTORE_CAP = 1e-6;
	   defparam CFLY_CAP = 100e-9;
`endif

defparam auto_stop_after  = 15*ms;
defparam printSimTimeStep = 0.1*ms;

integer stairs_done=0;
integer count_pwm_edges=0;

// suppress undriven Z
wire #(5*us,100) api_started = `TOP_DIG_PATH.mupet.sync_in_application;
//wire #(5*us,100) api_started = `TOP_DIG_PATH.mupet.mupet_activation.in_application;
wire               ov_vboost = /*`TOP_DIG_PATH.ms_ov_boost | */`TOP_DIG_PATH.ms_ov_boosti; // taken out: delays the
wire               uv_vboost = /*`TOP_DIG_PATH.ms_uv_boost | */`TOP_DIG_PATH.ms_uv_boosti; //   measurement triggers
wire  cpdrv_dig  = cmph[`A_CPDRV];
wire  vboost_dig = cmph[`A_VBOOST];

parameter real	  vs_val		= 12
		, vlin_val		= vs_val
		, v_vdda_min		= 3.1		// defaults for 3V operation
		, v_vdda_max		= 3.6
		, v_vdda5_min		= 4.9		// defaults for 5V operation
		, v_vdda5_max		= 5.1

// spec for VCPDRV
		, v_cpdrv_min10V 	= 7.0,	v_cpdrv_max10V  = vs_val+0.1	// VSM > 10V
		, v_cpdrv_min8V	  	= 5.5,	v_cpdrv_max8V   = vs_val+0.1	// 8V < VSM < 10V
		, v_cpdrv_minlt8V 	= 3.0,	v_cpdrv_maxlt8V = vs_val+0.1	// VSM < 8V

// spec declarion OV,UV -> add V(VSM) before use
		, v_boost_min10V 	= 7.0,	v_boost_max10V  = 9.5	// VSM > 10V
		, v_boost_min8V	  	= 5.5,	v_boost_max8V   = 9.5	// 8V < VSM < 10V
		, v_boost_minlt8V 	= 3.0,	v_boost_maxlt8V = 8.0	// VSM < 8V
		, v_boost_ov_min  	= 9.5,	v_boost_ov_max  = 10.5	// overvolt
		, v_boost_uv_min  	= 6.3,	v_boost_uv_max  = 6.6	// undervolt
		, v_uvov_hyst_min	= 0.200,v_uvov_hyst_max	= 0.4+0.05 // hysteresis OV, UV comps
;
real		  i_vdda		= 0	// store measurements
		, i_vdda_pre_mrb		= 0
		, i_vddd		= 0
		, ibias			= 0	// measure OVUV bias (or others)
		, v_vboost		= 0
		, v_vsm			= 0
		, v_cpdrv		= 0

		, limit_vcpdrv_min 	= v_cpdrv_min10V  
		, limit_vcpdrv_max 	= v_cpdrv_max10V  

		// must add v(VSM) to all values 
		, limit_vboost_min 	= v_boost_min10V // +v_vsm  //  // initial with vsm=0.0V
		, limit_vboost_max 	= v_boost_max10V // +v_vsm  //   
		, limit_uv_min		= v_boost_uv_min // +v_vsm  // 
		, limit_uv_max		= v_boost_uv_max // +v_vsm  // 
		, limit_ov_min		= v_boost_ov_min // +v_vsm  // 
		, limit_ov_max		= v_boost_ov_max // +v_vsm  // 
		;

// Charge Pump application circuitry
`ifndef HL_MODEL
BAV99 DVFLYUPR (PIN_VSM,VFLY);
BAV99 DVFLYLWR (VFLY,PIN_VBOOST);
capacitor #(.c(CSTORE_CAP)) C_STORE (PIN_VBOOST, PIN_VSM);
capacitor #(.c(CFLY_CAP)) C_FLY (VFLY, PIN_CPDRV);

analog begin
  I(PIN_VBOOST,PIN_VSM) <+ transition(V(PIN_VBOOST,PIN_VSM)*en_cp_fets_load*1/RLOAD_FETs_CP,0,1u);
  I(PIN_VBOOST,PIN_VSM) <+ transition(V(PIN_VBOOST,PIN_VSM)*en_cp_pdrv_load*1/RLOAD_pDRV_CP,0,1u);
end

//`else
//initial #0 no_meas_errors = 1; // disable analog measurement fails, default by HL_MODEL now
`endif
`ifndef VSM_VOLTAGE
	`define VSM_VOLTAGE 48
`endif
`include "../environment/helpers.vams"
initial #0 begin:main_sequence
	IF.reset;
	#1
	ramp_vs_vsm(12, `VSM_VOLTAGE, 10e-6);

	#100 wait(MRB === 1); sim_msg = "RESET DONE";
	$display("%0s================================================================%0s", blue, normal);
	$display("%0s***** %0s / %0s (sdf: %0s) *****%0s", blue,`TC, `TC_CONF, del_case,normal);
	$display("%0s================================================================%0s", blue, normal);
	$display("%0s Simulation %0s driver charge pump behavior%0s", blue, dev_name, normal);
	$display("%0s\t- controlled by Flash program%0s", blue, normal);
	$display("%0s INFO\tVS\t%.1fV (from %m, at start)%0s",blue,vs_val,normal);
	$display("%0s INFO\t%0sTemp\t%.0fC %0s%0s(from amsControlSpectre.scs)%0s",blue,bold,$temperature-273.15,normal,blue,normal);
	$display("%0s================================================================%0s", blue, normal);

    `ifndef HL_MODEL
        i_vdda_pre_mrb = 1e6*($cds_get_analog_value("top.CHIP.AA_DIE.SUSY_SHELL.AA_ANALOG.A_SUPPLY_SYSTEM_CORE.A_REG_V3V3.V3V3" ,"flow") ); // scale to uA as limit
    `endif
	@(posedge api_started) sim_msg = "IN_APPLICATION";
	en_cp_pdrv_load = 1;
	IF.rd( `A_VSM, GET_VOUT, v_vsm);
	`ifndef SV_MODEL
	i_vdda = 1e12*($cds_get_analog_value("top.CHIP.AA_DIE.SUSY_SHELL.AA_ANALOG.A_SUPPLY_SYSTEM_CORE.A_REG_V3V3.V3V3" ,"flow") ); 
	
	measAnalog("V_VBGA", $cds_get_analog_value("top.CHIP.AA_DIE.SUSY_SHELL.AA_ANALOG.A_SUPPLY_SYSTEM_CORE.VBG_A", "potential"), 1.16, 1.22, 1.0, "V"); 
	measAnalog("V_VBGD", $cds_get_analog_value("top.CHIP.AA_DIE.SUSY_SHELL.AA_ANALOG.A_SUPPLY_SYSTEM_CORE.VBG_D", "potential"), 1.16, 1.22, 1.0, "V"); 
	`endif
   // check 5V option limits, compared to current measurement from 3V it should not increase too much
	`ifndef SV_MODEL
	measAnalog("I_VDDA", abs(i_vdda), abs(i_vdda_pre_mrb)*0.5, abs(i_vdda_pre_mrb)*1.9, 1e-6, "uA");
	measAnalog("V_VDDA", V(PIN_VDDA), v_vdda_min, v_vdda_max, 1.0, "V"); // limits set by used TC mode
	`endif
	wait(`TOP_DIG_PATH.ms_en_cp);
	$display("\tCharge pump is enabled now");

	wait(!`TOP_DIG_PATH.ms_uv_boost);
	en_cp_fets_load = 1;

	#(300*us);
	`ifndef SV_MODEL 
		IF.rd(`A_VSM, GET_VOUT, v_vsm);
		IF.rd(`A_VBOOST, GET_VOUT, v_vboost);
		case (1) 
			(v_vsm > 10):				 measAnalog("MLX81346-218_VBOOST_HI", v_vboost-v_vsm, 7.5, 10, 1, "V");
			(v_vsm > 8 && v_vsm < 10): measAnalog("MLX81346-219_VBOOST_NOM", v_vboost-v_vsm, 5.5, 9.5, 1, "V");
			(v_vsm < 8): 				 measAnalog("MLX81346-220_VBOOST_NOM", v_vboost-v_vsm, 3.5, 8, 1, "V");
		endcase
	`endif

	

	wait(!`TOP_DIG_PATH.ms_en_cp);
	`ifdef HL_MODEL
	$display("\t%m stops sim for digital model (remaining stimuli are analog function, focus to charging)");
	end_simulation(errors);
     `endif
	 // en_cp_fets_load = 0;
	trigger_val_uv = 0; // Hysteresis faulty, because of high VBOOST slew rate
	wait(`TOP_DIG_PATH.ms_en_cp);
	$display("\twait for charge pump got disabled (to drive from Pin)");
	wait(!`TOP_DIG_PATH.ms_en_cp);
	en_cp_fets_load = 0;
	en_cp_pdrv_load = 0;

	#(100*us);    
	IF.wr(`A_VBOOST, SET_TR, 0.1e-6);
	IF.rd(`A_VBOOST, GET_VOUT, v_vboost);	
	IF.wr(`A_VBOOST, SET_VOUT, v_vboost);	
	IF.wr(`A_VBOOST, SET_SW, CLOSE);
	
	IF.rd(`A_VSM, GET_VOUT, v_vsm);
	IF.wr(`A_VBOOST, SET_TR, `CP_TR/2);
	IF.wr(`A_VBOOST, SET_VOUT, v_vsm + 12);	// ramp up to ov - question, why moe took very high voltage

	$display("\tOverdrive VBOOST to 23V/500us ramp, wait for OV");

	@(posedge ov_vboost) #(20*us) 
	IF.wr(`A_VBOOST, SET_TR, `CP_TR);
	IF.wr(`A_VBOOST, SET_VOUT, v_vsm);

	$display("\tPulldown VBOOST to 5V/500us ramp, wait for UV");
	@ (posedge uv_vboost) IF.wr(`A_VBOOST, SET_SW, OPEN);
	#(1*ms) end_simulation(errors);

end

//////////////////////////////   MEASUREMENTS   //////////////////////////////

always@(`TOP_DIG_PATH.ms_tr_cp[3:0])
	case(`TOP_DIG_PATH.ms_tr_cp[3:0])
	4'h0: begin RLOAD_FETs_CP = (8)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (LOAD_VOLTAGE+8)/     ILOAD_pDRV_CP; end
	4'h1: begin RLOAD_FETs_CP = (8.5)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (8.5)/   ILOAD_pDRV_CP; end
	4'h2: begin RLOAD_FETs_CP = (9)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (9)/     ILOAD_pDRV_CP; end
	4'h3: begin RLOAD_FETs_CP = (9.4)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (9.4)/   ILOAD_pDRV_CP; end
	4'h4: begin RLOAD_FETs_CP = (9.9)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (9.9)/   ILOAD_pDRV_CP; end
	4'h5: begin RLOAD_FETs_CP = (10.3)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (10.3)/  ILOAD_pDRV_CP; end
	4'h6: begin RLOAD_FETs_CP = (10.7)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (10.7)/  ILOAD_pDRV_CP; end
	4'h7: begin RLOAD_FETs_CP = (11.2)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (11.2)/  ILOAD_pDRV_CP; end
	4'h8: begin RLOAD_FETs_CP = (4.6)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (4.6)/   ILOAD_pDRV_CP; end
	4'h9: begin RLOAD_FETs_CP = (5)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (5)/     ILOAD_pDRV_CP; end
	4'hA: begin RLOAD_FETs_CP = (5.4)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (5.4)/   ILOAD_pDRV_CP; end
	4'hB: begin RLOAD_FETs_CP = (5.9)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (5.9)/   ILOAD_pDRV_CP; end
	4'hC: begin RLOAD_FETs_CP = (6.3)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (6.3)/   ILOAD_pDRV_CP; end
	4'hD: begin RLOAD_FETs_CP = (6.8)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (6.8)/   ILOAD_pDRV_CP; end
	4'hE: begin RLOAD_FETs_CP = (7.2)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (7.2)/   ILOAD_pDRV_CP; end
	4'hF: begin RLOAD_FETs_CP = (7.7)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (7.7)/   ILOAD_pDRV_CP; end
	default: begin RLOAD_FETs_CP = (4.6)/ILOAD_FETs_CP;	RLOAD_pDRV_CP = (4.6)/   ILOAD_pDRV_CP; end
	endcase

always @(`TOP_DIG_PATH.ms_tr_cp[3:0]) if (api_started===1) #(200*us) 
	begin
	IF.rd(`A_VSM, GET_VOUT, v_vsm);
	@(posedge vboost_dig) #(us);
	IF.rd(`A_VBOOST, GET_VOUT, v_vboost);
	`ifndef SV_MODEL
	@(posedge cpdrv_dig) #(us) IF.rd(`A_CPDRV, GET_VOUT, v_cpdrv);
	#0 measAnalog("V_VBOOST", v_vboost, limit_vboost_min, limit_vboost_max, 1.0, "V"); 
	#0 measAnalog("V_CPDRV",  v_cpdrv,  limit_vcpdrv_min, limit_vcpdrv_max, 1.0, "V"); 
	`endif
	end								

//////////////////////////////   MESSAGES   //////////////////////////////
always @(v_vsm) // triggered by measurement update
	if      (v_vsm > 10)	begin
				limit_vboost_min=v_boost_min10V+v_vsm; limit_vcpdrv_min=v_cpdrv_min10V;
				limit_vboost_max=v_boost_max10V+v_vsm; limit_vcpdrv_max=v_cpdrv_max10V;
				end
	else if (v_vsm > 8) 	begin
				limit_vboost_min=v_boost_min8V+v_vsm; limit_vcpdrv_min=v_cpdrv_min8V;
				limit_vboost_max=v_boost_max8V+v_vsm; limit_vcpdrv_max=v_cpdrv_max8V;
				end
	else /* vsm < 8V */	begin
				limit_vboost_min=v_boost_minlt8V+v_vsm; limit_vcpdrv_min=v_cpdrv_minlt8V;
				limit_vboost_max=v_boost_maxlt8V+v_vsm; limit_vcpdrv_max=v_cpdrv_maxlt8V;
				end
/*
		, v_boost_min10V 	= 7.0,	v_boost_max10V  = 9.5	// VSM > 10V
		, v_boost_min8V	  	= 5.5,	v_boost_max8V   = 9.5	// 8V < VSM < 10V
		, v_boost_minlt8V 	= 3.0,	v_boost_maxlt8V = 8.0	// VSM < 8V
		, v_boost_ov_min  	= 9.5,	v_boost_ov_max  = 10.5	// overvolt
		, v_boost_uv_min  	= 6.3,	v_boost_uv_max  = 6.5	// undervolt
		, v_uvov_hyst_min	= 0.2,	v_uvov_hyst_max	= 0.3 

*/

always @(ov_vboost) if (api_started===1) #5 begin // let it settle
	IF.rd(`A_VSM,    GET_VOUT, v_vsm);
	IF.rd(`A_VBOOST, GET_VOUT, v_vboost);
	IF.rd(`A_CPDRV,  GET_VOUT, v_cpdrv);
	limit_uv_min=v_boost_uv_min+v_vsm;	limit_uv_max=v_boost_uv_max+v_vsm;
	limit_ov_min=v_boost_ov_min+v_vsm;	limit_ov_max=v_boost_ov_max+v_vsm;
`ifndef HL_MODEL
        ibias = 1e6*abs($cds_get_analog_value("top.CHIP.AA_DIE.CP_SHELL.OVUV_VBOOST_I.IPD1U" ,"flow") ); 
`else	ibias=1; `endif
	#0 measAnalog("ibias_1u_pd(OV,UV)", ibias, 0.7, 1.5, 1.0, "uA"); // log only
  	if (ov_vboost) begin
		$display("\t%0sOV(VBOOST) triggered at %.3fV%0s",bold,v_vboost,normal);
		// measAnalog("V(VSM)", v_vsm, 3, 20, 1.0, "V"); // log only
		measAnalog("OV_VBOOST_LH", v_vboost, limit_ov_min, limit_ov_max, 1.0, "V");
    `ifndef SV_MODEL
		if (trigger_val_ov != 0) begin
			measAnalog("VBOOST_OV_HYST", abs(v_vboost - trigger_val_ov), v_uvov_hyst_min, v_uvov_hyst_max, 1.0, "V");
		end
    `endif
		  trigger_val_ov = v_vboost;
		end
		else begin
      $display("\t%0sOV(VBOOST) released at %.3fV%0s",bold,v_vboost,normal);
    // measAnalog("V(VSM)", v_vsm, 3, 20, 1.0, "V"); // log only
      measAnalog("OV_VBOOST_HL", v_vboost, limit_ov_min, limit_ov_max, 1.0, "V");
      `ifndef SV_MODEL
      if (trigger_val_ov != 0) begin
        measAnalog("VBOOST_OV_HYST", abs(v_vboost - trigger_val_ov), v_uvov_hyst_min, v_uvov_hyst_max, 1.0, "V");
      end
      `endif
      trigger_val_ov = v_vboost;
		end
	end
always @(uv_vboost) if (api_started===1) #5 begin // let it settle
	IF.rd(`A_VSM,    GET_VOUT, v_vsm);
	IF.rd(`A_VBOOST, GET_VOUT, v_vboost);
	IF.rd(`A_CPDRV,  GET_VOUT, v_cpdrv);
	limit_uv_min=v_boost_uv_min+v_vsm-v_uvov_hyst_max;	limit_uv_max=v_boost_uv_max+v_vsm+v_uvov_hyst_max;
	limit_ov_min=v_boost_ov_min+v_vsm-v_uvov_hyst_max;	limit_ov_max=v_boost_ov_max+v_vsm+v_uvov_hyst_max;
`ifndef HL_MODEL
        ibias = 1e6*abs($cds_get_analog_value("top.CHIP.AA_DIE.CP_SHELL.OVUV_VBOOST_I.IPD1U" ,"flow") ); 
`else	ibias=1; `endif
	#0 measAnalog("ibias_1u_pd(OV,UV)", ibias, 0.7, 1.5, 1.0, "uA"); // log only
	
	if (uv_vboost) begin
		$display("\t%0sUV(VBOOST) triggered at %.3fV%0s",bold,v_vboost,normal);
		// measAnalog("V(VSM)", v_vsm, 3, 20, 1.0, "V"); // log only
		measAnalog("UV_VBOOST_LH", v_vboost, limit_uv_min, limit_uv_max, 1.0, "V");
    `ifndef SV_MODEL
		if (trigger_val_uv != 0) begin
			measAnalog("VBOOST_UV_HYST", abs(v_vboost - trigger_val_uv), v_uvov_hyst_min, v_uvov_hyst_max, 1.0, "V");
		end
    `endif
		trigger_val_uv = v_vboost;
		end
		else begin
		$display("\t%0sUV(VBOOST) released at %.3fV%0s",bold,v_vboost,normal);
		// measAnalog("V(VSM)", v_vsm, 3, 20, 1.0, "V"); // log only
		measAnalog("UV_VBOOST_HL", v_vboost, limit_uv_min, limit_uv_max, 1.0, "V"); //slightly above, but release is not critical
    `ifndef SV_MODEL
		if (trigger_val_uv != 0) begin
			measAnalog("VBOOST_UV_HYST", abs(v_vboost - trigger_val_uv), v_uvov_hyst_min, v_uvov_hyst_max, 1.0, "V");
		end
    `endif
		trigger_val_uv = v_vboost;
		end
	end

always @(posedge `TOP_DIG_PATH.ms_switch_vdda_to_5v)
      $display("\n\t%0sVDDA 5V option gets activated (by asm)%0s",bold,normal);
      
always @(IO) if (MRB & api_started)
      #5 $display("*** INFO *** @%t %m: IO[11:0] = %04b_%04b_%04b", $time, IO[11:8], IO[7:4], IO[3:0]);

initial #50 if (`TC == "tc_cp") set_term_title("Driver charge pump ");
           else                 set_term_title("Driver charge pump VDDA=5V");
// vi:syntax=verilogams
/////////////////////////////////////////////////////////////////////////////////////////////////
// Testcase file: this file contains the stimuli/story of what needs to be simulated
//
// Following defines are available if full CMD-line approach is used:
//       `BENCH: name of the simulation bench used
//       `TC: name of the testcase
//       `TC_CONF: name of the testcase configuration
//       `RUN: name of the run
//
//       `AMS_RESULTS_DIR: directory where simulation results are stored (/localrundirs/<user>/<project>/<rev>/BENCH/RUN/TC/TC_CONF/)
//       `TESTCASE_DIR: testcase directory  (/mixed/simulations/BENCH/TC)
//       `SETUP_DIR: setup directory (/mixed/simulations/BENCH/setup)
//       `DUT_DIR: dut directory (/mixed/simulations/BENCH/dut)
//       `ENVIRONMENT_DIR: environment directory  (/mixed/simulations/BENCH/environment)
//       `OUTPUT_DIR: output log directory (/mixed/simulations/BENCH/TC/output__RUN__TC_CONF)
//       `NETLIST_DIR: netlist directory (/analog/release</sandbox>/LIB/CELL/VIEW)
//
//
/////////////////////////////////////////////////////////////////////////////////////////////////
//
//  Description: Example ASM program execution
//
//  1) Software generates a staircase output on IO's
//  2) Software turns on PWM on IO's
//
//  $Author: pts $
//  $Revision: 1.4 $
//  $Date: Tue Jun 15 10:49:09 2021 $
//  $Source: /mnt/dss/syncdata/dss.colo.elex.be/3411/server_vault/Projects/m81346/vBA/mixed/simulations/top/tc_cp/tc_vams.inc.rca $
//
/////////////////////////////////////////////////////////////////////////////////////////////////
//
// 2018/11/27 svj - initial version
`ifndef TC `define TC "dummy4compile" `endif

`ifndef CP_TR `define CP_TR 500e-6 `endif
`ifndef VLOAD `define VLOAD 12	`endif
reg en_cp_fets_load; 	initial en_cp_fets_load = 1'b0;
reg en_cp_pdrv_load; 	initial en_cp_pdrv_load = 1'b0;

parameter real ILOAD_FETs_CP		= 4.8e-3	`ifndef HL_MODEL from (0:inf) `endif;		// [A] external predriver FETs
//parameter real ILOAD_FETs_CP		= 100e-3	`ifndef HL_MODEL from (0:inf) `endif;		// [A] external predriver FETs
parameter real ILOAD_pDRV_CP		= 1.2e-3	`ifndef HL_MODEL from (0:inf) `endif;		// [A] external predriver circuitry
parameter real LOAD_VOLTAGE = `VLOAD; // legacy value from older versions

real trigger_val_uv, trigger_val_ov;

real RLOAD_FETs_CP;
real RLOAD_pDRV_CP;

initial RLOAD_FETs_CP = (LOAD_VOLTAGE+4.6)/ILOAD_FETs_CP;
initial RLOAD_pDRV_CP = (LOAD_VOLTAGE+4.6)/ILOAD_pDRV_CP;

initial trigger_val_uv = 0; 
initial trigger_val_ov = 0;

parameter CSTORE_CAP	 = 3e-6; // Storage Capacity Value of Chargepump 
parameter CFLY_CAP		 = 600e-9; // Flycap Capacity Value of Chargepump

`ifdef OLD_CAPS
	   defparam CSTORE_CAP = 1e-6;
	   defparam CFLY_CAP = 100e-9;
`endif

defparam auto_stop_after  = 15*ms;
defparam printSimTimeStep = 0.1*ms;

integer stairs_done=0;
integer count_pwm_edges=0;

// suppress undriven Z
wire #(5*us,100) api_started = `TOP_DIG_PATH.mupet.sync_in_application;
//wire #(5*us,100) api_started = `TOP_DIG_PATH.mupet.mupet_activation.in_application;
wire               ov_vboost = /*`TOP_DIG_PATH.ms_ov_boost | */`TOP_DIG_PATH.ms_ov_boosti; // taken out: delays the
wire               uv_vboost = /*`TOP_DIG_PATH.ms_uv_boost | */`TOP_DIG_PATH.ms_uv_boosti; //   measurement triggers
wire  cpdrv_dig  = cmph[`A_CPDRV];
wire  vboost_dig = cmph[`A_VBOOST];

parameter real	  vs_val		= 12
		, vlin_val		= vs_val
		, v_vdda_min		= 3.1		// defaults for 3V operation
		, v_vdda_max		= 3.6
		, v_vdda5_min		= 4.9		// defaults for 5V operation
		, v_vdda5_max		= 5.1

// spec for VCPDRV
		, v_cpdrv_min10V 	= 7.0,	v_cpdrv_max10V  = vs_val+0.1	// VSM > 10V
		, v_cpdrv_min8V	  	= 5.5,	v_cpdrv_max8V   = vs_val+0.1	// 8V < VSM < 10V
		, v_cpdrv_minlt8V 	= 3.0,	v_cpdrv_maxlt8V = vs_val+0.1	// VSM < 8V

// spec declarion OV,UV -> add V(VSM) before use
		, v_boost_min10V 	= 7.0,	v_boost_max10V  = 9.5	// VSM > 10V
		, v_boost_min8V	  	= 5.5,	v_boost_max8V   = 9.5	// 8V < VSM < 10V
		, v_boost_minlt8V 	= 3.0,	v_boost_maxlt8V = 8.0	// VSM < 8V
		, v_boost_ov_min  	= 9.5,	v_boost_ov_max  = 10.5	// overvolt
		, v_boost_uv_min  	= 6.3,	v_boost_uv_max  = 6.6	// undervolt
		, v_uvov_hyst_min	= 0.200,v_uvov_hyst_max	= 0.4+0.05 // hysteresis OV, UV comps
;
real		  i_vdda		= 0	// store measurements
		, i_vdda_pre_mrb		= 0
		, i_vddd		= 0
		, ibias			= 0	// measure OVUV bias (or others)
		, v_vboost		= 0
		, v_vsm			= 0
		, v_cpdrv		= 0

		, limit_vcpdrv_min 	= v_cpdrv_min10V  
		, limit_vcpdrv_max 	= v_cpdrv_max10V  

		// must add v(VSM) to all values 
		, limit_vboost_min 	= v_boost_min10V // +v_vsm  //  // initial with vsm=0.0V
		, limit_vboost_max 	= v_boost_max10V // +v_vsm  //   
		, limit_uv_min		= v_boost_uv_min // +v_vsm  // 
		, limit_uv_max		= v_boost_uv_max // +v_vsm  // 
		, limit_ov_min		= v_boost_ov_min // +v_vsm  // 
		, limit_ov_max		= v_boost_ov_max // +v_vsm  // 
		;

// Charge Pump application circuitry
`ifndef HL_MODEL
BAV99 DVFLYUPR (PIN_VSM,VFLY);
BAV99 DVFLYLWR (VFLY,PIN_VBOOST);
capacitor #(.c(CSTORE_CAP)) C_STORE (PIN_VBOOST, PIN_VSM);
capacitor #(.c(CFLY_CAP)) C_FLY (VFLY, PIN_CPDRV);

analog begin
  I(PIN_VBOOST,PIN_VSM) <+ transition(V(PIN_VBOOST,PIN_VSM)*en_cp_fets_load*1/RLOAD_FETs_CP,0,1u);
  I(PIN_VBOOST,PIN_VSM) <+ transition(V(PIN_VBOOST,PIN_VSM)*en_cp_pdrv_load*1/RLOAD_pDRV_CP,0,1u);
end

//`else
//initial #0 no_meas_errors = 1; // disable analog measurement fails, default by HL_MODEL now
`endif
`ifndef VSM_VOLTAGE
	`define VSM_VOLTAGE 48
`endif
`include "../environment/helpers.vams"
initial #0 begin:main_sequence
	IF.reset;
	#1
	ramp_vs_vsm(12, `VSM_VOLTAGE, 10e-6);

	#100 wait(MRB === 1); sim_msg = "RESET DONE";
	$display("%0s================================================================%0s", blue, normal);
	$display("%0s***** %0s / %0s (sdf: %0s) *****%0s", blue,`TC, `TC_CONF, del_case,normal);
	$display("%0s================================================================%0s", blue, normal);
	$display("%0s Simulation %0s driver charge pump behavior%0s", blue, dev_name, normal);
	$display("%0s\t- controlled by Flash program%0s", blue, normal);
	$display("%0s INFO\tVS\t%.1fV (from %m, at start)%0s",blue,vs_val,normal);
	$display("%0s INFO\t%0sTemp\t%.0fC %0s%0s(from amsControlSpectre.scs)%0s",blue,bold,$temperature-273.15,normal,blue,normal);
	$display("%0s================================================================%0s", blue, normal);

    `ifndef HL_MODEL
        i_vdda_pre_mrb = 1e6*($cds_get_analog_value("top.CHIP.AA_DIE.SUSY_SHELL.AA_ANALOG.A_SUPPLY_SYSTEM_CORE.A_REG_V3V3.V3V3" ,"flow") ); // scale to uA as limit
    `endif
	@(posedge api_started) sim_msg = "IN_APPLICATION";
	en_cp_pdrv_load = 1;
	IF.rd( `A_VSM, GET_VOUT, v_vsm);
	`ifndef SV_MODEL
	i_vdda = 1e12*($cds_get_analog_value("top.CHIP.AA_DIE.SUSY_SHELL.AA_ANALOG.A_SUPPLY_SYSTEM_CORE.A_REG_V3V3.V3V3" ,"flow") ); 
	
	measAnalog("V_VBGA", $cds_get_analog_value("top.CHIP.AA_DIE.SUSY_SHELL.AA_ANALOG.A_SUPPLY_SYSTEM_CORE.VBG_A", "potential"), 1.16, 1.22, 1.0, "V"); 
	measAnalog("V_VBGD", $cds_get_analog_value("top.CHIP.AA_DIE.SUSY_SHELL.AA_ANALOG.A_SUPPLY_SYSTEM_CORE.VBG_D", "potential"), 1.16, 1.22, 1.0, "V"); 
	`endif
   // check 5V option limits, compared to current measurement from 3V it should not increase too much
	`ifndef SV_MODEL
	measAnalog("I_VDDA", abs(i_vdda), abs(i_vdda_pre_mrb)*0.5, abs(i_vdda_pre_mrb)*1.9, 1e-6, "uA");
	measAnalog("V_VDDA", V(PIN_VDDA), v_vdda_min, v_vdda_max, 1.0, "V"); // limits set by used TC mode
	`endif
	wait(`TOP_DIG_PATH.ms_en_cp);
	$display("\tCharge pump is enabled now");

	wait(!`TOP_DIG_PATH.ms_uv_boost);
	en_cp_fets_load = 1;

	#(300*us);
	`ifndef SV_MODEL 
		IF.rd(`A_VSM, GET_VOUT, v_vsm);
		IF.rd(`A_VBOOST, GET_VOUT, v_vboost);
		case (1) 
			(v_vsm > 10):				 measAnalog("MLX81346-218_VBOOST_HI", v_vboost-v_vsm, 7.5, 10, 1, "V");
			(v_vsm > 8 && v_vsm < 10): measAnalog("MLX81346-219_VBOOST_NOM", v_vboost-v_vsm, 5.5, 9.5, 1, "V");
			(v_vsm < 8): 				 measAnalog("MLX81346-220_VBOOST_NOM", v_vboost-v_vsm, 3.5, 8, 1, "V");
		endcase
	`endif

	

	wait(!`TOP_DIG_PATH.ms_en_cp);
	`ifdef HL_MODEL
	$display("\t%m stops sim for digital model (remaining stimuli are analog function, focus to charging)");
	end_simulation(errors);
     `endif
	 // en_cp_fets_load = 0;
	trigger_val_uv = 0; // Hysteresis faulty, because of high VBOOST slew rate
	wait(`TOP_DIG_PATH.ms_en_cp);
	$display("\twait for charge pump got disabled (to drive from Pin)");
	wait(!`TOP_DIG_PATH.ms_en_cp);
	en_cp_fets_load = 0;
	en_cp_pdrv_load = 0;

	#(100*us);    
	IF.wr(`A_VBOOST, SET_TR, 0.1e-6);
	IF.rd(`A_VBOOST, GET_VOUT, v_vboost);	
	IF.wr(`A_VBOOST, SET_VOUT, v_vboost);	
	IF.wr(`A_VBOOST, SET_SW, CLOSE);
	
	IF.rd(`A_VSM, GET_VOUT, v_vsm);
	IF.wr(`A_VBOOST, SET_TR, `CP_TR/2);
	IF.wr(`A_VBOOST, SET_VOUT, v_vsm + 12);	// ramp up to ov - question, why moe took very high voltage

	$display("\tOverdrive VBOOST to 23V/500us ramp, wait for OV");

	@(posedge ov_vboost) #(20*us) 
	IF.wr(`A_VBOOST, SET_TR, `CP_TR);
	IF.wr(`A_VBOOST, SET_VOUT, v_vsm);

	$display("\tPulldown VBOOST to 5V/500us ramp, wait for UV");
	@ (posedge uv_vboost) IF.wr(`A_VBOOST, SET_SW, OPEN);
	#(1*ms) end_simulation(errors);

end

//////////////////////////////   MEASUREMENTS   //////////////////////////////

always@(`TOP_DIG_PATH.ms_tr_cp[3:0])
	case(`TOP_DIG_PATH.ms_tr_cp[3:0])
	4'h0: begin RLOAD_FETs_CP = (8)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (LOAD_VOLTAGE+8)/     ILOAD_pDRV_CP; end
	4'h1: begin RLOAD_FETs_CP = (8.5)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (8.5)/   ILOAD_pDRV_CP; end
	4'h2: begin RLOAD_FETs_CP = (9)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (9)/     ILOAD_pDRV_CP; end
	4'h3: begin RLOAD_FETs_CP = (9.4)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (9.4)/   ILOAD_pDRV_CP; end
	4'h4: begin RLOAD_FETs_CP = (9.9)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (9.9)/   ILOAD_pDRV_CP; end
	4'h5: begin RLOAD_FETs_CP = (10.3)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (10.3)/  ILOAD_pDRV_CP; end
	4'h6: begin RLOAD_FETs_CP = (10.7)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (10.7)/  ILOAD_pDRV_CP; end
	4'h7: begin RLOAD_FETs_CP = (11.2)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (11.2)/  ILOAD_pDRV_CP; end
	4'h8: begin RLOAD_FETs_CP = (4.6)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (4.6)/   ILOAD_pDRV_CP; end
	4'h9: begin RLOAD_FETs_CP = (5)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (5)/     ILOAD_pDRV_CP; end
	4'hA: begin RLOAD_FETs_CP = (5.4)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (5.4)/   ILOAD_pDRV_CP; end
	4'hB: begin RLOAD_FETs_CP = (5.9)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (5.9)/   ILOAD_pDRV_CP; end
	4'hC: begin RLOAD_FETs_CP = (6.3)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (6.3)/   ILOAD_pDRV_CP; end
	4'hD: begin RLOAD_FETs_CP = (6.8)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (6.8)/   ILOAD_pDRV_CP; end
	4'hE: begin RLOAD_FETs_CP = (7.2)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (7.2)/   ILOAD_pDRV_CP; end
	4'hF: begin RLOAD_FETs_CP = (7.7)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (7.7)/   ILOAD_pDRV_CP; end
	default: begin RLOAD_FETs_CP = (4.6)/ILOAD_FETs_CP;	RLOAD_pDRV_CP = (4.6)/   ILOAD_pDRV_CP; end
	endcase

always @(`TOP_DIG_PATH.ms_tr_cp[3:0]) if (api_started===1) #(200*us) 
	begin
	IF.rd(`A_VSM, GET_VOUT, v_vsm);
	@(posedge vboost_dig) #(us);
	IF.rd(`A_VBOOST, GET_VOUT, v_vboost);
	`ifndef SV_MODEL
	@(posedge cpdrv_dig) #(us) IF.rd(`A_CPDRV, GET_VOUT, v_cpdrv);
	#0 measAnalog("V_VBOOST", v_vboost, limit_vboost_min, limit_vboost_max, 1.0, "V"); 
	#0 measAnalog("V_CPDRV",  v_cpdrv,  limit_vcpdrv_min, limit_vcpdrv_max, 1.0, "V"); 
	`endif
	end								

//////////////////////////////   MESSAGES   //////////////////////////////
always @(v_vsm) // triggered by measurement update
	if      (v_vsm > 10)	begin
				limit_vboost_min=v_boost_min10V+v_vsm; limit_vcpdrv_min=v_cpdrv_min10V;
				limit_vboost_max=v_boost_max10V+v_vsm; limit_vcpdrv_max=v_cpdrv_max10V;
				end
	else if (v_vsm > 8) 	begin
				limit_vboost_min=v_boost_min8V+v_vsm; limit_vcpdrv_min=v_cpdrv_min8V;
				limit_vboost_max=v_boost_max8V+v_vsm; limit_vcpdrv_max=v_cpdrv_max8V;
				end
	else /* vsm < 8V */	begin
				limit_vboost_min=v_boost_minlt8V+v_vsm; limit_vcpdrv_min=v_cpdrv_minlt8V;
				limit_vboost_max=v_boost_maxlt8V+v_vsm; limit_vcpdrv_max=v_cpdrv_maxlt8V;
				end
/*
		, v_boost_min10V 	= 7.0,	v_boost_max10V  = 9.5	// VSM > 10V
		, v_boost_min8V	  	= 5.5,	v_boost_max8V   = 9.5	// 8V < VSM < 10V
		, v_boost_minlt8V 	= 3.0,	v_boost_maxlt8V = 8.0	// VSM < 8V
		, v_boost_ov_min  	= 9.5,	v_boost_ov_max  = 10.5	// overvolt
		, v_boost_uv_min  	= 6.3,	v_boost_uv_max  = 6.5	// undervolt
		, v_uvov_hyst_min	= 0.2,	v_uvov_hyst_max	= 0.3 

*/

always @(ov_vboost) if (api_started===1) #5 begin // let it settle
	IF.rd(`A_VSM,    GET_VOUT, v_vsm);
	IF.rd(`A_VBOOST, GET_VOUT, v_vboost);
	IF.rd(`A_CPDRV,  GET_VOUT, v_cpdrv);
	limit_uv_min=v_boost_uv_min+v_vsm;	limit_uv_max=v_boost_uv_max+v_vsm;
	limit_ov_min=v_boost_ov_min+v_vsm;	limit_ov_max=v_boost_ov_max+v_vsm;
`ifndef HL_MODEL
        ibias = 1e6*abs($cds_get_analog_value("top.CHIP.AA_DIE.CP_SHELL.OVUV_VBOOST_I.IPD1U" ,"flow") ); 
`else	ibias=1; `endif
	#0 measAnalog("ibias_1u_pd(OV,UV)", ibias, 0.7, 1.5, 1.0, "uA"); // log only
  	if (ov_vboost) begin
		$display("\t%0sOV(VBOOST) triggered at %.3fV%0s",bold,v_vboost,normal);
		// measAnalog("V(VSM)", v_vsm, 3, 20, 1.0, "V"); // log only
		measAnalog("OV_VBOOST_LH", v_vboost, limit_ov_min, limit_ov_max, 1.0, "V");
    `ifndef SV_MODEL
		if (trigger_val_ov != 0) begin
			measAnalog("VBOOST_OV_HYST", abs(v_vboost - trigger_val_ov), v_uvov_hyst_min, v_uvov_hyst_max, 1.0, "V");
		end
    `endif
		  trigger_val_ov = v_vboost;
		end
		else begin
      $display("\t%0sOV(VBOOST) released at %.3fV%0s",bold,v_vboost,normal);
    // measAnalog("V(VSM)", v_vsm, 3, 20, 1.0, "V"); // log only
      measAnalog("OV_VBOOST_HL", v_vboost, limit_ov_min, limit_ov_max, 1.0, "V");
      `ifndef SV_MODEL
      if (trigger_val_ov != 0) begin
        measAnalog("VBOOST_OV_HYST", abs(v_vboost - trigger_val_ov), v_uvov_hyst_min, v_uvov_hyst_max, 1.0, "V");
      end
      `endif
      trigger_val_ov = v_vboost;
		end
	end
always @(uv_vboost) if (api_started===1) #5 begin // let it settle
	IF.rd(`A_VSM,    GET_VOUT, v_vsm);
	IF.rd(`A_VBOOST, GET_VOUT, v_vboost);
	IF.rd(`A_CPDRV,  GET_VOUT, v_cpdrv);
	limit_uv_min=v_boost_uv_min+v_vsm-v_uvov_hyst_max;	limit_uv_max=v_boost_uv_max+v_vsm+v_uvov_hyst_max;
	limit_ov_min=v_boost_ov_min+v_vsm-v_uvov_hyst_max;	limit_ov_max=v_boost_ov_max+v_vsm+v_uvov_hyst_max;
`ifndef HL_MODEL
        ibias = 1e6*abs($cds_get_analog_value("top.CHIP.AA_DIE.CP_SHELL.OVUV_VBOOST_I.IPD1U" ,"flow") ); 
`else	ibias=1; `endif
	#0 measAnalog("ibias_1u_pd(OV,UV)", ibias, 0.7, 1.5, 1.0, "uA"); // log only
	
	if (uv_vboost) begin
		$display("\t%0sUV(VBOOST) triggered at %.3fV%0s",bold,v_vboost,normal);
		// measAnalog("V(VSM)", v_vsm, 3, 20, 1.0, "V"); // log only
		measAnalog("UV_VBOOST_LH", v_vboost, limit_uv_min, limit_uv_max, 1.0, "V");
    `ifndef SV_MODEL
		if (trigger_val_uv != 0) begin
			measAnalog("VBOOST_UV_HYST", abs(v_vboost - trigger_val_uv), v_uvov_hyst_min, v_uvov_hyst_max, 1.0, "V");
		end
    `endif
		trigger_val_uv = v_vboost;
		end
		else begin
		$display("\t%0sUV(VBOOST) released at %.3fV%0s",bold,v_vboost,normal);
		// measAnalog("V(VSM)", v_vsm, 3, 20, 1.0, "V"); // log only
		measAnalog("UV_VBOOST_HL", v_vboost, limit_uv_min, limit_uv_max, 1.0, "V"); //slightly above, but release is not critical
    `ifndef SV_MODEL
		if (trigger_val_uv != 0) begin
			measAnalog("VBOOST_UV_HYST", abs(v_vboost - trigger_val_uv), v_uvov_hyst_min, v_uvov_hyst_max, 1.0, "V");
		end
    `endif
		trigger_val_uv = v_vboost;
		end
	end

always @(posedge `TOP_DIG_PATH.ms_switch_vdda_to_5v)
      $display("\n\t%0sVDDA 5V option gets activated (by asm)%0s",bold,normal);
      
always @(IO) if (MRB & api_started)
      #5 $display("*** INFO *** @%t %m: IO[11:0] = %04b_%04b_%04b", $time, IO[11:8], IO[7:4], IO[3:0]);

initial #50 if (`TC == "tc_cp") set_term_title("Driver charge pump ");
           else                 set_term_title("Driver charge pump VDDA=5V");
// vi:syntax=verilogams
/////////////////////////////////////////////////////////////////////////////////////////////////
// Testcase file: this file contains the stimuli/story of what needs to be simulated
//
// Following defines are available if full CMD-line approach is used:
//       `BENCH: name of the simulation bench used
//       `TC: name of the testcase
//       `TC_CONF: name of the testcase configuration
//       `RUN: name of the run
//
//       `AMS_RESULTS_DIR: directory where simulation results are stored (/localrundirs/<user>/<project>/<rev>/BENCH/RUN/TC/TC_CONF/)
//       `TESTCASE_DIR: testcase directory  (/mixed/simulations/BENCH/TC)
//       `SETUP_DIR: setup directory (/mixed/simulations/BENCH/setup)
//       `DUT_DIR: dut directory (/mixed/simulations/BENCH/dut)
//       `ENVIRONMENT_DIR: environment directory  (/mixed/simulations/BENCH/environment)
//       `OUTPUT_DIR: output log directory (/mixed/simulations/BENCH/TC/output__RUN__TC_CONF)
//       `NETLIST_DIR: netlist directory (/analog/release</sandbox>/LIB/CELL/VIEW)
//
//
/////////////////////////////////////////////////////////////////////////////////////////////////
//
//  Description: Example ASM program execution
//
//  1) Software generates a staircase output on IO's
//  2) Software turns on PWM on IO's
//
//  $Author: pts $
//  $Revision: 1.4 $
//  $Date: Tue Jun 15 10:49:09 2021 $
//  $Source: /mnt/dss/syncdata/dss.colo.elex.be/3411/server_vault/Projects/m81346/vBA/mixed/simulations/top/tc_cp/tc_vams.inc.rca $
//
/////////////////////////////////////////////////////////////////////////////////////////////////
//
// 2018/11/27 svj - initial version
`ifndef TC `define TC "dummy4compile" `endif

`ifndef CP_TR `define CP_TR 500e-6 `endif
`ifndef VLOAD `define VLOAD 12	`endif
reg en_cp_fets_load; 	initial en_cp_fets_load = 1'b0;
reg en_cp_pdrv_load; 	initial en_cp_pdrv_load = 1'b0;

parameter real ILOAD_FETs_CP		= 4.8e-3	`ifndef HL_MODEL from (0:inf) `endif;		// [A] external predriver FETs
//parameter real ILOAD_FETs_CP		= 100e-3	`ifndef HL_MODEL from (0:inf) `endif;		// [A] external predriver FETs
parameter real ILOAD_pDRV_CP		= 1.2e-3	`ifndef HL_MODEL from (0:inf) `endif;		// [A] external predriver circuitry
parameter real LOAD_VOLTAGE = `VLOAD; // legacy value from older versions

real trigger_val_uv, trigger_val_ov;

real RLOAD_FETs_CP;
real RLOAD_pDRV_CP;

initial RLOAD_FETs_CP = (LOAD_VOLTAGE+4.6)/ILOAD_FETs_CP;
initial RLOAD_pDRV_CP = (LOAD_VOLTAGE+4.6)/ILOAD_pDRV_CP;

initial trigger_val_uv = 0; 
initial trigger_val_ov = 0;

parameter CSTORE_CAP	 = 3e-6; // Storage Capacity Value of Chargepump 
parameter CFLY_CAP		 = 600e-9; // Flycap Capacity Value of Chargepump

`ifdef OLD_CAPS
	   defparam CSTORE_CAP = 1e-6;
	   defparam CFLY_CAP = 100e-9;
`endif

defparam auto_stop_after  = 15*ms;
defparam printSimTimeStep = 0.1*ms;

integer stairs_done=0;
integer count_pwm_edges=0;

// suppress undriven Z
wire #(5*us,100) api_started = `TOP_DIG_PATH.mupet.sync_in_application;
//wire #(5*us,100) api_started = `TOP_DIG_PATH.mupet.mupet_activation.in_application;
wire               ov_vboost = /*`TOP_DIG_PATH.ms_ov_boost | */`TOP_DIG_PATH.ms_ov_boosti; // taken out: delays the
wire               uv_vboost = /*`TOP_DIG_PATH.ms_uv_boost | */`TOP_DIG_PATH.ms_uv_boosti; //   measurement triggers
wire  cpdrv_dig  = cmph[`A_CPDRV];
wire  vboost_dig = cmph[`A_VBOOST];

parameter real	  vs_val		= 12
		, vlin_val		= vs_val
		, v_vdda_min		= 3.1		// defaults for 3V operation
		, v_vdda_max		= 3.6
		, v_vdda5_min		= 4.9		// defaults for 5V operation
		, v_vdda5_max		= 5.1

// spec for VCPDRV
		, v_cpdrv_min10V 	= 7.0,	v_cpdrv_max10V  = vs_val+0.1	// VSM > 10V
		, v_cpdrv_min8V	  	= 5.5,	v_cpdrv_max8V   = vs_val+0.1	// 8V < VSM < 10V
		, v_cpdrv_minlt8V 	= 3.0,	v_cpdrv_maxlt8V = vs_val+0.1	// VSM < 8V

// spec declarion OV,UV -> add V(VSM) before use
		, v_boost_min10V 	= 7.0,	v_boost_max10V  = 9.5	// VSM > 10V
		, v_boost_min8V	  	= 5.5,	v_boost_max8V   = 9.5	// 8V < VSM < 10V
		, v_boost_minlt8V 	= 3.0,	v_boost_maxlt8V = 8.0	// VSM < 8V
		, v_boost_ov_min  	= 9.5,	v_boost_ov_max  = 10.5	// overvolt
		, v_boost_uv_min  	= 6.3,	v_boost_uv_max  = 6.6	// undervolt
		, v_uvov_hyst_min	= 0.200,v_uvov_hyst_max	= 0.4+0.05 // hysteresis OV, UV comps
;
real		  i_vdda		= 0	// store measurements
		, i_vdda_pre_mrb		= 0
		, i_vddd		= 0
		, ibias			= 0	// measure OVUV bias (or others)
		, v_vboost		= 0
		, v_vsm			= 0
		, v_cpdrv		= 0

		, limit_vcpdrv_min 	= v_cpdrv_min10V  
		, limit_vcpdrv_max 	= v_cpdrv_max10V  

		// must add v(VSM) to all values 
		, limit_vboost_min 	= v_boost_min10V // +v_vsm  //  // initial with vsm=0.0V
		, limit_vboost_max 	= v_boost_max10V // +v_vsm  //   
		, limit_uv_min		= v_boost_uv_min // +v_vsm  // 
		, limit_uv_max		= v_boost_uv_max // +v_vsm  // 
		, limit_ov_min		= v_boost_ov_min // +v_vsm  // 
		, limit_ov_max		= v_boost_ov_max // +v_vsm  // 
		;

// Charge Pump application circuitry
`ifndef HL_MODEL
BAV99 DVFLYUPR (PIN_VSM,VFLY);
BAV99 DVFLYLWR (VFLY,PIN_VBOOST);
capacitor #(.c(CSTORE_CAP)) C_STORE (PIN_VBOOST, PIN_VSM);
capacitor #(.c(CFLY_CAP)) C_FLY (VFLY, PIN_CPDRV);

analog begin
  I(PIN_VBOOST,PIN_VSM) <+ transition(V(PIN_VBOOST,PIN_VSM)*en_cp_fets_load*1/RLOAD_FETs_CP,0,1u);
  I(PIN_VBOOST,PIN_VSM) <+ transition(V(PIN_VBOOST,PIN_VSM)*en_cp_pdrv_load*1/RLOAD_pDRV_CP,0,1u);
end

//`else
//initial #0 no_meas_errors = 1; // disable analog measurement fails, default by HL_MODEL now
`endif
`ifndef VSM_VOLTAGE
	`define VSM_VOLTAGE 48
`endif
`include "../environment/helpers.vams"
initial #0 begin:main_sequence
	IF.reset;
	#1
	ramp_vs_vsm(12, `VSM_VOLTAGE, 10e-6);

	#100 wait(MRB === 1); sim_msg = "RESET DONE";
	$display("%0s================================================================%0s", blue, normal);
	$display("%0s***** %0s / %0s (sdf: %0s) *****%0s", blue,`TC, `TC_CONF, del_case,normal);
	$display("%0s================================================================%0s", blue, normal);
	$display("%0s Simulation %0s driver charge pump behavior%0s", blue, dev_name, normal);
	$display("%0s\t- controlled by Flash program%0s", blue, normal);
	$display("%0s INFO\tVS\t%.1fV (from %m, at start)%0s",blue,vs_val,normal);
	$display("%0s INFO\t%0sTemp\t%.0fC %0s%0s(from amsControlSpectre.scs)%0s",blue,bold,$temperature-273.15,normal,blue,normal);
	$display("%0s================================================================%0s", blue, normal);

    `ifndef HL_MODEL
        i_vdda_pre_mrb = 1e6*($cds_get_analog_value("top.CHIP.AA_DIE.SUSY_SHELL.AA_ANALOG.A_SUPPLY_SYSTEM_CORE.A_REG_V3V3.V3V3" ,"flow") ); // scale to uA as limit
    `endif
	@(posedge api_started) sim_msg = "IN_APPLICATION";
	en_cp_pdrv_load = 1;
	IF.rd( `A_VSM, GET_VOUT, v_vsm);
	`ifndef SV_MODEL
	i_vdda = 1e12*($cds_get_analog_value("top.CHIP.AA_DIE.SUSY_SHELL.AA_ANALOG.A_SUPPLY_SYSTEM_CORE.A_REG_V3V3.V3V3" ,"flow") ); 
	
	measAnalog("V_VBGA", $cds_get_analog_value("top.CHIP.AA_DIE.SUSY_SHELL.AA_ANALOG.A_SUPPLY_SYSTEM_CORE.VBG_A", "potential"), 1.16, 1.22, 1.0, "V"); 
	measAnalog("V_VBGD", $cds_get_analog_value("top.CHIP.AA_DIE.SUSY_SHELL.AA_ANALOG.A_SUPPLY_SYSTEM_CORE.VBG_D", "potential"), 1.16, 1.22, 1.0, "V"); 
	`endif
   // check 5V option limits, compared to current measurement from 3V it should not increase too much
	`ifndef SV_MODEL
	measAnalog("I_VDDA", abs(i_vdda), abs(i_vdda_pre_mrb)*0.5, abs(i_vdda_pre_mrb)*1.9, 1e-6, "uA");
	measAnalog("V_VDDA", V(PIN_VDDA), v_vdda_min, v_vdda_max, 1.0, "V"); // limits set by used TC mode
	`endif
	wait(`TOP_DIG_PATH.ms_en_cp);
	$display("\tCharge pump is enabled now");

	wait(!`TOP_DIG_PATH.ms_uv_boost);
	en_cp_fets_load = 1;

	#(300*us);
	`ifndef SV_MODEL 
		IF.rd(`A_VSM, GET_VOUT, v_vsm);
		IF.rd(`A_VBOOST, GET_VOUT, v_vboost);
		case (1) 
			(v_vsm > 10):				 measAnalog("MLX81346-218_VBOOST_HI", v_vboost-v_vsm, 7.5, 10, 1, "V");
			(v_vsm > 8 && v_vsm < 10): measAnalog("MLX81346-219_VBOOST_NOM", v_vboost-v_vsm, 5.5, 9.5, 1, "V");
			(v_vsm < 8): 				 measAnalog("MLX81346-220_VBOOST_NOM", v_vboost-v_vsm, 3.5, 8, 1, "V");
		endcase
	`endif

	

	wait(!`TOP_DIG_PATH.ms_en_cp);
	`ifdef HL_MODEL
	$display("\t%m stops sim for digital model (remaining stimuli are analog function, focus to charging)");
	end_simulation(errors);
     `endif
	 // en_cp_fets_load = 0;
	trigger_val_uv = 0; // Hysteresis faulty, because of high VBOOST slew rate
	wait(`TOP_DIG_PATH.ms_en_cp);
	$display("\twait for charge pump got disabled (to drive from Pin)");
	wait(!`TOP_DIG_PATH.ms_en_cp);
	en_cp_fets_load = 0;
	en_cp_pdrv_load = 0;

	#(100*us);    
	IF.wr(`A_VBOOST, SET_TR, 0.1e-6);
	IF.rd(`A_VBOOST, GET_VOUT, v_vboost);	
	IF.wr(`A_VBOOST, SET_VOUT, v_vboost);	
	IF.wr(`A_VBOOST, SET_SW, CLOSE);
	
	IF.rd(`A_VSM, GET_VOUT, v_vsm);
	IF.wr(`A_VBOOST, SET_TR, `CP_TR/2);
	IF.wr(`A_VBOOST, SET_VOUT, v_vsm + 12);	// ramp up to ov - question, why moe took very high voltage

	$display("\tOverdrive VBOOST to 23V/500us ramp, wait for OV");

	@(posedge ov_vboost) #(20*us) 
	IF.wr(`A_VBOOST, SET_TR, `CP_TR);
	IF.wr(`A_VBOOST, SET_VOUT, v_vsm);

	$display("\tPulldown VBOOST to 5V/500us ramp, wait for UV");
	@ (posedge uv_vboost) IF.wr(`A_VBOOST, SET_SW, OPEN);
	#(1*ms) end_simulation(errors);

end

//////////////////////////////   MEASUREMENTS   //////////////////////////////

always@(`TOP_DIG_PATH.ms_tr_cp[3:0])
	case(`TOP_DIG_PATH.ms_tr_cp[3:0])
	4'h0: begin RLOAD_FETs_CP = (8)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (LOAD_VOLTAGE+8)/     ILOAD_pDRV_CP; end
	4'h1: begin RLOAD_FETs_CP = (8.5)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (8.5)/   ILOAD_pDRV_CP; end
	4'h2: begin RLOAD_FETs_CP = (9)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (9)/     ILOAD_pDRV_CP; end
	4'h3: begin RLOAD_FETs_CP = (9.4)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (9.4)/   ILOAD_pDRV_CP; end
	4'h4: begin RLOAD_FETs_CP = (9.9)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (9.9)/   ILOAD_pDRV_CP; end
	4'h5: begin RLOAD_FETs_CP = (10.3)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (10.3)/  ILOAD_pDRV_CP; end
	4'h6: begin RLOAD_FETs_CP = (10.7)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (10.7)/  ILOAD_pDRV_CP; end
	4'h7: begin RLOAD_FETs_CP = (11.2)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (11.2)/  ILOAD_pDRV_CP; end
	4'h8: begin RLOAD_FETs_CP = (4.6)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (4.6)/   ILOAD_pDRV_CP; end
	4'h9: begin RLOAD_FETs_CP = (5)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (5)/     ILOAD_pDRV_CP; end
	4'hA: begin RLOAD_FETs_CP = (5.4)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (5.4)/   ILOAD_pDRV_CP; end
	4'hB: begin RLOAD_FETs_CP = (5.9)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (5.9)/   ILOAD_pDRV_CP; end
	4'hC: begin RLOAD_FETs_CP = (6.3)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (6.3)/   ILOAD_pDRV_CP; end
	4'hD: begin RLOAD_FETs_CP = (6.8)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (6.8)/   ILOAD_pDRV_CP; end
	4'hE: begin RLOAD_FETs_CP = (7.2)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (7.2)/   ILOAD_pDRV_CP; end
	4'hF: begin RLOAD_FETs_CP = (7.7)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (7.7)/   ILOAD_pDRV_CP; end
	default: begin RLOAD_FETs_CP = (4.6)/ILOAD_FETs_CP;	RLOAD_pDRV_CP = (4.6)/   ILOAD_pDRV_CP; end
	endcase

always @(`TOP_DIG_PATH.ms_tr_cp[3:0]) if (api_started===1) #(200*us) 
	begin
	IF.rd(`A_VSM, GET_VOUT, v_vsm);
	@(posedge vboost_dig) #(us);
	IF.rd(`A_VBOOST, GET_VOUT, v_vboost);
	`ifndef SV_MODEL
	@(posedge cpdrv_dig) #(us) IF.rd(`A_CPDRV, GET_VOUT, v_cpdrv);
	#0 measAnalog("V_VBOOST", v_vboost, limit_vboost_min, limit_vboost_max, 1.0, "V"); 
	#0 measAnalog("V_CPDRV",  v_cpdrv,  limit_vcpdrv_min, limit_vcpdrv_max, 1.0, "V"); 
	`endif
	end								

//////////////////////////////   MESSAGES   //////////////////////////////
always @(v_vsm) // triggered by measurement update
	if      (v_vsm > 10)	begin
				limit_vboost_min=v_boost_min10V+v_vsm; limit_vcpdrv_min=v_cpdrv_min10V;
				limit_vboost_max=v_boost_max10V+v_vsm; limit_vcpdrv_max=v_cpdrv_max10V;
				end
	else if (v_vsm > 8) 	begin
				limit_vboost_min=v_boost_min8V+v_vsm; limit_vcpdrv_min=v_cpdrv_min8V;
				limit_vboost_max=v_boost_max8V+v_vsm; limit_vcpdrv_max=v_cpdrv_max8V;
				end
	else /* vsm < 8V */	begin
				limit_vboost_min=v_boost_minlt8V+v_vsm; limit_vcpdrv_min=v_cpdrv_minlt8V;
				limit_vboost_max=v_boost_maxlt8V+v_vsm; limit_vcpdrv_max=v_cpdrv_maxlt8V;
				end
/*
		, v_boost_min10V 	= 7.0,	v_boost_max10V  = 9.5	// VSM > 10V
		, v_boost_min8V	  	= 5.5,	v_boost_max8V   = 9.5	// 8V < VSM < 10V
		, v_boost_minlt8V 	= 3.0,	v_boost_maxlt8V = 8.0	// VSM < 8V
		, v_boost_ov_min  	= 9.5,	v_boost_ov_max  = 10.5	// overvolt
		, v_boost_uv_min  	= 6.3,	v_boost_uv_max  = 6.5	// undervolt
		, v_uvov_hyst_min	= 0.2,	v_uvov_hyst_max	= 0.3 

*/

always @(ov_vboost) if (api_started===1) #5 begin // let it settle
	IF.rd(`A_VSM,    GET_VOUT, v_vsm);
	IF.rd(`A_VBOOST, GET_VOUT, v_vboost);
	IF.rd(`A_CPDRV,  GET_VOUT, v_cpdrv);
	limit_uv_min=v_boost_uv_min+v_vsm;	limit_uv_max=v_boost_uv_max+v_vsm;
	limit_ov_min=v_boost_ov_min+v_vsm;	limit_ov_max=v_boost_ov_max+v_vsm;
`ifndef HL_MODEL
        ibias = 1e6*abs($cds_get_analog_value("top.CHIP.AA_DIE.CP_SHELL.OVUV_VBOOST_I.IPD1U" ,"flow") ); 
`else	ibias=1; `endif
	#0 measAnalog("ibias_1u_pd(OV,UV)", ibias, 0.7, 1.5, 1.0, "uA"); // log only
  	if (ov_vboost) begin
		$display("\t%0sOV(VBOOST) triggered at %.3fV%0s",bold,v_vboost,normal);
		// measAnalog("V(VSM)", v_vsm, 3, 20, 1.0, "V"); // log only
		measAnalog("OV_VBOOST_LH", v_vboost, limit_ov_min, limit_ov_max, 1.0, "V");
    `ifndef SV_MODEL
		if (trigger_val_ov != 0) begin
			measAnalog("VBOOST_OV_HYST", abs(v_vboost - trigger_val_ov), v_uvov_hyst_min, v_uvov_hyst_max, 1.0, "V");
		end
    `endif
		  trigger_val_ov = v_vboost;
		end
		else begin
      $display("\t%0sOV(VBOOST) released at %.3fV%0s",bold,v_vboost,normal);
    // measAnalog("V(VSM)", v_vsm, 3, 20, 1.0, "V"); // log only
      measAnalog("OV_VBOOST_HL", v_vboost, limit_ov_min, limit_ov_max, 1.0, "V");
      `ifndef SV_MODEL
      if (trigger_val_ov != 0) begin
        measAnalog("VBOOST_OV_HYST", abs(v_vboost - trigger_val_ov), v_uvov_hyst_min, v_uvov_hyst_max, 1.0, "V");
      end
      `endif
      trigger_val_ov = v_vboost;
		end
	end
always @(uv_vboost) if (api_started===1) #5 begin // let it settle
	IF.rd(`A_VSM,    GET_VOUT, v_vsm);
	IF.rd(`A_VBOOST, GET_VOUT, v_vboost);
	IF.rd(`A_CPDRV,  GET_VOUT, v_cpdrv);
	limit_uv_min=v_boost_uv_min+v_vsm-v_uvov_hyst_max;	limit_uv_max=v_boost_uv_max+v_vsm+v_uvov_hyst_max;
	limit_ov_min=v_boost_ov_min+v_vsm-v_uvov_hyst_max;	limit_ov_max=v_boost_ov_max+v_vsm+v_uvov_hyst_max;
`ifndef HL_MODEL
        ibias = 1e6*abs($cds_get_analog_value("top.CHIP.AA_DIE.CP_SHELL.OVUV_VBOOST_I.IPD1U" ,"flow") ); 
`else	ibias=1; `endif
	#0 measAnalog("ibias_1u_pd(OV,UV)", ibias, 0.7, 1.5, 1.0, "uA"); // log only
	
	if (uv_vboost) begin
		$display("\t%0sUV(VBOOST) triggered at %.3fV%0s",bold,v_vboost,normal);
		// measAnalog("V(VSM)", v_vsm, 3, 20, 1.0, "V"); // log only
		measAnalog("UV_VBOOST_LH", v_vboost, limit_uv_min, limit_uv_max, 1.0, "V");
    `ifndef SV_MODEL
		if (trigger_val_uv != 0) begin
			measAnalog("VBOOST_UV_HYST", abs(v_vboost - trigger_val_uv), v_uvov_hyst_min, v_uvov_hyst_max, 1.0, "V");
		end
    `endif
		trigger_val_uv = v_vboost;
		end
		else begin
		$display("\t%0sUV(VBOOST) released at %.3fV%0s",bold,v_vboost,normal);
		// measAnalog("V(VSM)", v_vsm, 3, 20, 1.0, "V"); // log only
		measAnalog("UV_VBOOST_HL", v_vboost, limit_uv_min, limit_uv_max, 1.0, "V"); //slightly above, but release is not critical
    `ifndef SV_MODEL
		if (trigger_val_uv != 0) begin
			measAnalog("VBOOST_UV_HYST", abs(v_vboost - trigger_val_uv), v_uvov_hyst_min, v_uvov_hyst_max, 1.0, "V");
		end
    `endif
		trigger_val_uv = v_vboost;
		end
	end

always @(posedge `TOP_DIG_PATH.ms_switch_vdda_to_5v)
      $display("\n\t%0sVDDA 5V option gets activated (by asm)%0s",bold,normal);
      
always @(IO) if (MRB & api_started)
      #5 $display("*** INFO *** @%t %m: IO[11:0] = %04b_%04b_%04b", $time, IO[11:8], IO[7:4], IO[3:0]);

initial #50 if (`TC == "tc_cp") set_term_title("Driver charge pump ");
           else                 set_term_title("Driver charge pump VDDA=5V");
// vi:syntax=verilogams
/////////////////////////////////////////////////////////////////////////////////////////////////
// Testcase file: this file contains the stimuli/story of what needs to be simulated
//
// Following defines are available if full CMD-line approach is used:
//       `BENCH: name of the simulation bench used
//       `TC: name of the testcase
//       `TC_CONF: name of the testcase configuration
//       `RUN: name of the run
//
//       `AMS_RESULTS_DIR: directory where simulation results are stored (/localrundirs/<user>/<project>/<rev>/BENCH/RUN/TC/TC_CONF/)
//       `TESTCASE_DIR: testcase directory  (/mixed/simulations/BENCH/TC)
//       `SETUP_DIR: setup directory (/mixed/simulations/BENCH/setup)
//       `DUT_DIR: dut directory (/mixed/simulations/BENCH/dut)
//       `ENVIRONMENT_DIR: environment directory  (/mixed/simulations/BENCH/environment)
//       `OUTPUT_DIR: output log directory (/mixed/simulations/BENCH/TC/output__RUN__TC_CONF)
//       `NETLIST_DIR: netlist directory (/analog/release</sandbox>/LIB/CELL/VIEW)
//
//
/////////////////////////////////////////////////////////////////////////////////////////////////
//
//  Description: Example ASM program execution
//
//  1) Software generates a staircase output on IO's
//  2) Software turns on PWM on IO's
//
//  $Author: pts $
//  $Revision: 1.4 $
//  $Date: Tue Jun 15 10:49:09 2021 $
//  $Source: /mnt/dss/syncdata/dss.colo.elex.be/3411/server_vault/Projects/m81346/vBA/mixed/simulations/top/tc_cp/tc_vams.inc.rca $
//
/////////////////////////////////////////////////////////////////////////////////////////////////
//
// 2018/11/27 svj - initial version
`ifndef TC `define TC "dummy4compile" `endif

`ifndef CP_TR `define CP_TR 500e-6 `endif
`ifndef VLOAD `define VLOAD 12	`endif
reg en_cp_fets_load; 	initial en_cp_fets_load = 1'b0;
reg en_cp_pdrv_load; 	initial en_cp_pdrv_load = 1'b0;

parameter real ILOAD_FETs_CP		= 4.8e-3	`ifndef HL_MODEL from (0:inf) `endif;		// [A] external predriver FETs
//parameter real ILOAD_FETs_CP		= 100e-3	`ifndef HL_MODEL from (0:inf) `endif;		// [A] external predriver FETs
parameter real ILOAD_pDRV_CP		= 1.2e-3	`ifndef HL_MODEL from (0:inf) `endif;		// [A] external predriver circuitry
parameter real LOAD_VOLTAGE = `VLOAD; // legacy value from older versions

real trigger_val_uv, trigger_val_ov;

real RLOAD_FETs_CP;
real RLOAD_pDRV_CP;

initial RLOAD_FETs_CP = (LOAD_VOLTAGE+4.6)/ILOAD_FETs_CP;
initial RLOAD_pDRV_CP = (LOAD_VOLTAGE+4.6)/ILOAD_pDRV_CP;

initial trigger_val_uv = 0; 
initial trigger_val_ov = 0;

parameter CSTORE_CAP	 = 3e-6; // Storage Capacity Value of Chargepump 
parameter CFLY_CAP		 = 600e-9; // Flycap Capacity Value of Chargepump

`ifdef OLD_CAPS
	   defparam CSTORE_CAP = 1e-6;
	   defparam CFLY_CAP = 100e-9;
`endif

defparam auto_stop_after  = 15*ms;
defparam printSimTimeStep = 0.1*ms;

integer stairs_done=0;
integer count_pwm_edges=0;

// suppress undriven Z
wire #(5*us,100) api_started = `TOP_DIG_PATH.mupet.sync_in_application;
//wire #(5*us,100) api_started = `TOP_DIG_PATH.mupet.mupet_activation.in_application;
wire               ov_vboost = /*`TOP_DIG_PATH.ms_ov_boost | */`TOP_DIG_PATH.ms_ov_boosti; // taken out: delays the
wire               uv_vboost = /*`TOP_DIG_PATH.ms_uv_boost | */`TOP_DIG_PATH.ms_uv_boosti; //   measurement triggers
wire  cpdrv_dig  = cmph[`A_CPDRV];
wire  vboost_dig = cmph[`A_VBOOST];

parameter real	  vs_val		= 12
		, vlin_val		= vs_val
		, v_vdda_min		= 3.1		// defaults for 3V operation
		, v_vdda_max		= 3.6
		, v_vdda5_min		= 4.9		// defaults for 5V operation
		, v_vdda5_max		= 5.1

// spec for VCPDRV
		, v_cpdrv_min10V 	= 7.0,	v_cpdrv_max10V  = vs_val+0.1	// VSM > 10V
		, v_cpdrv_min8V	  	= 5.5,	v_cpdrv_max8V   = vs_val+0.1	// 8V < VSM < 10V
		, v_cpdrv_minlt8V 	= 3.0,	v_cpdrv_maxlt8V = vs_val+0.1	// VSM < 8V

// spec declarion OV,UV -> add V(VSM) before use
		, v_boost_min10V 	= 7.0,	v_boost_max10V  = 9.5	// VSM > 10V
		, v_boost_min8V	  	= 5.5,	v_boost_max8V   = 9.5	// 8V < VSM < 10V
		, v_boost_minlt8V 	= 3.0,	v_boost_maxlt8V = 8.0	// VSM < 8V
		, v_boost_ov_min  	= 9.5,	v_boost_ov_max  = 10.5	// overvolt
		, v_boost_uv_min  	= 6.3,	v_boost_uv_max  = 6.6	// undervolt
		, v_uvov_hyst_min	= 0.200,v_uvov_hyst_max	= 0.4+0.05 // hysteresis OV, UV comps
;
real		  i_vdda		= 0	// store measurements
		, i_vdda_pre_mrb		= 0
		, i_vddd		= 0
		, ibias			= 0	// measure OVUV bias (or others)
		, v_vboost		= 0
		, v_vsm			= 0
		, v_cpdrv		= 0

		, limit_vcpdrv_min 	= v_cpdrv_min10V  
		, limit_vcpdrv_max 	= v_cpdrv_max10V  

		// must add v(VSM) to all values 
		, limit_vboost_min 	= v_boost_min10V // +v_vsm  //  // initial with vsm=0.0V
		, limit_vboost_max 	= v_boost_max10V // +v_vsm  //   
		, limit_uv_min		= v_boost_uv_min // +v_vsm  // 
		, limit_uv_max		= v_boost_uv_max // +v_vsm  // 
		, limit_ov_min		= v_boost_ov_min // +v_vsm  // 
		, limit_ov_max		= v_boost_ov_max // +v_vsm  // 
		;

// Charge Pump application circuitry
`ifndef HL_MODEL
BAV99 DVFLYUPR (PIN_VSM,VFLY);
BAV99 DVFLYLWR (VFLY,PIN_VBOOST);
capacitor #(.c(CSTORE_CAP)) C_STORE (PIN_VBOOST, PIN_VSM);
capacitor #(.c(CFLY_CAP)) C_FLY (VFLY, PIN_CPDRV);

analog begin
  I(PIN_VBOOST,PIN_VSM) <+ transition(V(PIN_VBOOST,PIN_VSM)*en_cp_fets_load*1/RLOAD_FETs_CP,0,1u);
  I(PIN_VBOOST,PIN_VSM) <+ transition(V(PIN_VBOOST,PIN_VSM)*en_cp_pdrv_load*1/RLOAD_pDRV_CP,0,1u);
end

//`else
//initial #0 no_meas_errors = 1; // disable analog measurement fails, default by HL_MODEL now
`endif
`ifndef VSM_VOLTAGE
	`define VSM_VOLTAGE 48
`endif
`include "../environment/helpers.vams"
initial #0 begin:main_sequence
	IF.reset;
	#1
	ramp_vs_vsm(12, `VSM_VOLTAGE, 10e-6);

	#100 wait(MRB === 1); sim_msg = "RESET DONE";
	$display("%0s================================================================%0s", blue, normal);
	$display("%0s***** %0s / %0s (sdf: %0s) *****%0s", blue,`TC, `TC_CONF, del_case,normal);
	$display("%0s================================================================%0s", blue, normal);
	$display("%0s Simulation %0s driver charge pump behavior%0s", blue, dev_name, normal);
	$display("%0s\t- controlled by Flash program%0s", blue, normal);
	$display("%0s INFO\tVS\t%.1fV (from %m, at start)%0s",blue,vs_val,normal);
	$display("%0s INFO\t%0sTemp\t%.0fC %0s%0s(from amsControlSpectre.scs)%0s",blue,bold,$temperature-273.15,normal,blue,normal);
	$display("%0s================================================================%0s", blue, normal);

    `ifndef HL_MODEL
        i_vdda_pre_mrb = 1e6*($cds_get_analog_value("top.CHIP.AA_DIE.SUSY_SHELL.AA_ANALOG.A_SUPPLY_SYSTEM_CORE.A_REG_V3V3.V3V3" ,"flow") ); // scale to uA as limit
    `endif
	@(posedge api_started) sim_msg = "IN_APPLICATION";
	en_cp_pdrv_load = 1;
	IF.rd( `A_VSM, GET_VOUT, v_vsm);
	`ifndef SV_MODEL
	i_vdda = 1e12*($cds_get_analog_value("top.CHIP.AA_DIE.SUSY_SHELL.AA_ANALOG.A_SUPPLY_SYSTEM_CORE.A_REG_V3V3.V3V3" ,"flow") ); 
	
	measAnalog("V_VBGA", $cds_get_analog_value("top.CHIP.AA_DIE.SUSY_SHELL.AA_ANALOG.A_SUPPLY_SYSTEM_CORE.VBG_A", "potential"), 1.16, 1.22, 1.0, "V"); 
	measAnalog("V_VBGD", $cds_get_analog_value("top.CHIP.AA_DIE.SUSY_SHELL.AA_ANALOG.A_SUPPLY_SYSTEM_CORE.VBG_D", "potential"), 1.16, 1.22, 1.0, "V"); 
	`endif
   // check 5V option limits, compared to current measurement from 3V it should not increase too much
	`ifndef SV_MODEL
	measAnalog("I_VDDA", abs(i_vdda), abs(i_vdda_pre_mrb)*0.5, abs(i_vdda_pre_mrb)*1.9, 1e-6, "uA");
	measAnalog("V_VDDA", V(PIN_VDDA), v_vdda_min, v_vdda_max, 1.0, "V"); // limits set by used TC mode
	`endif
	wait(`TOP_DIG_PATH.ms_en_cp);
	$display("\tCharge pump is enabled now");

	wait(!`TOP_DIG_PATH.ms_uv_boost);
	en_cp_fets_load = 1;

	#(300*us);
	`ifndef SV_MODEL 
		IF.rd(`A_VSM, GET_VOUT, v_vsm);
		IF.rd(`A_VBOOST, GET_VOUT, v_vboost);
		case (1) 
			(v_vsm > 10):				 measAnalog("MLX81346-218_VBOOST_HI", v_vboost-v_vsm, 7.5, 10, 1, "V");
			(v_vsm > 8 && v_vsm < 10): measAnalog("MLX81346-219_VBOOST_NOM", v_vboost-v_vsm, 5.5, 9.5, 1, "V");
			(v_vsm < 8): 				 measAnalog("MLX81346-220_VBOOST_NOM", v_vboost-v_vsm, 3.5, 8, 1, "V");
		endcase
	`endif

	

	wait(!`TOP_DIG_PATH.ms_en_cp);
	`ifdef HL_MODEL
	$display("\t%m stops sim for digital model (remaining stimuli are analog function, focus to charging)");
	end_simulation(errors);
     `endif
	 // en_cp_fets_load = 0;
	trigger_val_uv = 0; // Hysteresis faulty, because of high VBOOST slew rate
	wait(`TOP_DIG_PATH.ms_en_cp);
	$display("\twait for charge pump got disabled (to drive from Pin)");
	wait(!`TOP_DIG_PATH.ms_en_cp);
	en_cp_fets_load = 0;
	en_cp_pdrv_load = 0;

	#(100*us);    
	IF.wr(`A_VBOOST, SET_TR, 0.1e-6);
	IF.rd(`A_VBOOST, GET_VOUT, v_vboost);	
	IF.wr(`A_VBOOST, SET_VOUT, v_vboost);	
	IF.wr(`A_VBOOST, SET_SW, CLOSE);
	
	IF.rd(`A_VSM, GET_VOUT, v_vsm);
	IF.wr(`A_VBOOST, SET_TR, `CP_TR/2);
	IF.wr(`A_VBOOST, SET_VOUT, v_vsm + 12);	// ramp up to ov - question, why moe took very high voltage

	$display("\tOverdrive VBOOST to 23V/500us ramp, wait for OV");

	@(posedge ov_vboost) #(20*us) 
	IF.wr(`A_VBOOST, SET_TR, `CP_TR);
	IF.wr(`A_VBOOST, SET_VOUT, v_vsm);

	$display("\tPulldown VBOOST to 5V/500us ramp, wait for UV");
	@ (posedge uv_vboost) IF.wr(`A_VBOOST, SET_SW, OPEN);
	#(1*ms) end_simulation(errors);

end

//////////////////////////////   MEASUREMENTS   //////////////////////////////

always@(`TOP_DIG_PATH.ms_tr_cp[3:0])
	case(`TOP_DIG_PATH.ms_tr_cp[3:0])
	4'h0: begin RLOAD_FETs_CP = (8)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (LOAD_VOLTAGE+8)/     ILOAD_pDRV_CP; end
	4'h1: begin RLOAD_FETs_CP = (8.5)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (8.5)/   ILOAD_pDRV_CP; end
	4'h2: begin RLOAD_FETs_CP = (9)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (9)/     ILOAD_pDRV_CP; end
	4'h3: begin RLOAD_FETs_CP = (9.4)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (9.4)/   ILOAD_pDRV_CP; end
	4'h4: begin RLOAD_FETs_CP = (9.9)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (9.9)/   ILOAD_pDRV_CP; end
	4'h5: begin RLOAD_FETs_CP = (10.3)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (10.3)/  ILOAD_pDRV_CP; end
	4'h6: begin RLOAD_FETs_CP = (10.7)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (10.7)/  ILOAD_pDRV_CP; end
	4'h7: begin RLOAD_FETs_CP = (11.2)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (11.2)/  ILOAD_pDRV_CP; end
	4'h8: begin RLOAD_FETs_CP = (4.6)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (4.6)/   ILOAD_pDRV_CP; end
	4'h9: begin RLOAD_FETs_CP = (5)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (5)/     ILOAD_pDRV_CP; end
	4'hA: begin RLOAD_FETs_CP = (5.4)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (5.4)/   ILOAD_pDRV_CP; end
	4'hB: begin RLOAD_FETs_CP = (5.9)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (5.9)/   ILOAD_pDRV_CP; end
	4'hC: begin RLOAD_FETs_CP = (6.3)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (6.3)/   ILOAD_pDRV_CP; end
	4'hD: begin RLOAD_FETs_CP = (6.8)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (6.8)/   ILOAD_pDRV_CP; end
	4'hE: begin RLOAD_FETs_CP = (7.2)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (7.2)/   ILOAD_pDRV_CP; end
	4'hF: begin RLOAD_FETs_CP = (7.7)/	ILOAD_FETs_CP;	RLOAD_pDRV_CP = (7.7)/   ILOAD_pDRV_CP; end
	default: begin RLOAD_FETs_CP = (4.6)/ILOAD_FETs_CP;	RLOAD_pDRV_CP = (4.6)/   ILOAD_pDRV_CP; end
	endcase

always @(`TOP_DIG_PATH.ms_tr_cp[3:0]) if (api_started===1) #(200*us) 
	begin
	IF.rd(`A_VSM, GET_VOUT, v_vsm);
	@(posedge vboost_dig) #(us);
	IF.rd(`A_VBOOST, GET_VOUT, v_vboost);
	`ifndef SV_MODEL
	@(posedge cpdrv_dig) #(us) IF.rd(`A_CPDRV, GET_VOUT, v_cpdrv);
	#0 measAnalog("V_VBOOST", v_vboost, limit_vboost_min, limit_vboost_max, 1.0, "V"); 
	#0 measAnalog("V_CPDRV",  v_cpdrv,  limit_vcpdrv_min, limit_vcpdrv_max, 1.0, "V"); 
	`endif
	end								

//////////////////////////////   MESSAGES   //////////////////////////////
always @(v_vsm) // triggered by measurement update
	if      (v_vsm > 10)	begin
				limit_vboost_min=v_boost_min10V+v_vsm; limit_vcpdrv_min=v_cpdrv_min10V;
				limit_vboost_max=v_boost_max10V+v_vsm; limit_vcpdrv_max=v_cpdrv_max10V;
				end
	else if (v_vsm > 8) 	begin
				limit_vboost_min=v_boost_min8V+v_vsm; limit_vcpdrv_min=v_cpdrv_min8V;
				limit_vboost_max=v_boost_max8V+v_vsm; limit_vcpdrv_max=v_cpdrv_max8V;
				end
	else /* vsm < 8V */	begin
				limit_vboost_min=v_boost_minlt8V+v_vsm; limit_vcpdrv_min=v_cpdrv_minlt8V;
				limit_vboost_max=v_boost_maxlt8V+v_vsm; limit_vcpdrv_max=v_cpdrv_maxlt8V;
				end
/*
		, v_boost_min10V 	= 7.0,	v_boost_max10V  = 9.5	// VSM > 10V
		, v_boost_min8V	  	= 5.5,	v_boost_max8V   = 9.5	// 8V < VSM < 10V
		, v_boost_minlt8V 	= 3.0,	v_boost_maxlt8V = 8.0	// VSM < 8V
		, v_boost_ov_min  	= 9.5,	v_boost_ov_max  = 10.5	// overvolt
		, v_boost_uv_min  	= 6.3,	v_boost_uv_max  = 6.5	// undervolt
		, v_uvov_hyst_min	= 0.2,	v_uvov_hyst_max	= 0.3 

*/

always @(ov_vboost) if (api_started===1) #5 begin // let it settle
	IF.rd(`A_VSM,    GET_VOUT, v_vsm);
	IF.rd(`A_VBOOST, GET_VOUT, v_vboost);
	IF.rd(`A_CPDRV,  GET_VOUT, v_cpdrv);
	limit_uv_min=v_boost_uv_min+v_vsm;	limit_uv_max=v_boost_uv_max+v_vsm;
	limit_ov_min=v_boost_ov_min+v_vsm;	limit_ov_max=v_boost_ov_max+v_vsm;
`ifndef HL_MODEL
        ibias = 1e6*abs($cds_get_analog_value("top.CHIP.AA_DIE.CP_SHELL.OVUV_VBOOST_I.IPD1U" ,"flow") ); 
`else	ibias=1; `endif
	#0 measAnalog("ibias_1u_pd(OV,UV)", ibias, 0.7, 1.5, 1.0, "uA"); // log only
  	if (ov_vboost) begin
		$display("\t%0sOV(VBOOST) triggered at %.3fV%0s",bold,v_vboost,normal);
		// measAnalog("V(VSM)", v_vsm, 3, 20, 1.0, "V"); // log only
		measAnalog("OV_VBOOST_LH", v_vboost, limit_ov_min, limit_ov_max, 1.0, "V");
    `ifndef SV_MODEL
		if (trigger_val_ov != 0) begin
			measAnalog("VBOOST_OV_HYST", abs(v_vboost - trigger_val_ov), v_uvov_hyst_min, v_uvov_hyst_max, 1.0, "V");
		end
    `endif
		  trigger_val_ov = v_vboost;
		end
		else begin
      $display("\t%0sOV(VBOOST) released at %.3fV%0s",bold,v_vboost,normal);
    // measAnalog("V(VSM)", v_vsm, 3, 20, 1.0, "V"); // log only
      measAnalog("OV_VBOOST_HL", v_vboost, limit_ov_min, limit_ov_max, 1.0, "V");
      `ifndef SV_MODEL
      if (trigger_val_ov != 0) begin
        measAnalog("VBOOST_OV_HYST", abs(v_vboost - trigger_val_ov), v_uvov_hyst_min, v_uvov_hyst_max, 1.0, "V");
      end
      `endif
      trigger_val_ov = v_vboost;
		end
	end
always @(uv_vboost) if (api_started===1) #5 begin // let it settle
	IF.rd(`A_VSM,    GET_VOUT, v_vsm);
	IF.rd(`A_VBOOST, GET_VOUT, v_vboost);
	IF.rd(`A_CPDRV,  GET_VOUT, v_cpdrv);
	limit_uv_min=v_boost_uv_min+v_vsm-v_uvov_hyst_max;	limit_uv_max=v_boost_uv_max+v_vsm+v_uvov_hyst_max;
	limit_ov_min=v_boost_ov_min+v_vsm-v_uvov_hyst_max;	limit_ov_max=v_boost_ov_max+v_vsm+v_uvov_hyst_max;
`ifndef HL_MODEL
        ibias = 1e6*abs($cds_get_analog_value("top.CHIP.AA_DIE.CP_SHELL.OVUV_VBOOST_I.IPD1U" ,"flow") ); 
`else	ibias=1; `endif
	#0 measAnalog("ibias_1u_pd(OV,UV)", ibias, 0.7, 1.5, 1.0, "uA"); // log only
	
	if (uv_vboost) begin
		$display("\t%0sUV(VBOOST) triggered at %.3fV%0s",bold,v_vboost,normal);
		// measAnalog("V(VSM)", v_vsm, 3, 20, 1.0, "V"); // log only
		measAnalog("UV_VBOOST_LH", v_vboost, limit_uv_min, limit_uv_max, 1.0, "V");
    `ifndef SV_MODEL
		if (trigger_val_uv != 0) begin
			measAnalog("VBOOST_UV_HYST", abs(v_vboost - trigger_val_uv), v_uvov_hyst_min, v_uvov_hyst_max, 1.0, "V");
		end
    `endif
		trigger_val_uv = v_vboost;
		end
		else begin
		$display("\t%0sUV(VBOOST) released at %.3fV%0s",bold,v_vboost,normal);
		// measAnalog("V(VSM)", v_vsm, 3, 20, 1.0, "V"); // log only
		measAnalog("UV_VBOOST_HL", v_vboost, limit_uv_min, limit_uv_max, 1.0, "V"); //slightly above, but release is not critical
    `ifndef SV_MODEL
		if (trigger_val_uv != 0) begin
			measAnalog("VBOOST_UV_HYST", abs(v_vboost - trigger_val_uv), v_uvov_hyst_min, v_uvov_hyst_max, 1.0, "V");
		end
    `endif
		trigger_val_uv = v_vboost;
		end
	end"""


def single_character_benchmark():
    input = "".join([txt for _ in range(10)])
    data = FileData(input)
    while not data.isEOF():
        data.consume()
    print(f"File parsed: Length: {len(input)}")


single_character_benchmark()
