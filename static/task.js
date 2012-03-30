
/**********************
* Domain general code *
**********************/

// Helper functions

// Assert functions stolen from 
// http://aymanh.com/9-javascript-tips-you-may-not-know#assertion
function AssertException(message) { this.message = message; }
AssertException.prototype.toString = function () {
	return 'AssertException: ' + this.message;
};

function assert(exp, message) {
	if (!exp) {
	  throw new AssertException(message);
	}
}

function insert_hidden_into_form(findex, name, value ) {
    var form = document.forms[findex];
    var hiddenField = document.createElement('input');
    hiddenField.setAttribute('type', 'hidden');
    hiddenField.setAttribute('name', name);
    hiddenField.setAttribute('value', value );
    form.appendChild( hiddenField );
}


// Preload images (not currently in use)
function imagepreload(src) 
{
	var heavyImage = new Image(); 
	heavyImage.src = src;
}

/** 
 * SUBSTITUTE PLACEHOLDERS WITH string values 
 * @param {String} str The string containing the placeholders 
 * @param {Array} arr The array of values to substitute 
 * From Fotiman on this forum:
 * http://www.webmasterworld.com/javascript/3484761.htm
 */ 
function substitute(str, arr) 
{ 
	var i, pattern, re, n = arr.length; 
	for (i = 0; i < n; i++) { 
		pattern = "\\{" + i + "\\}"; 
		re = new RegExp(pattern, "g"); 
		str = str.replace(re, arr[i]); 
	} 
	return str; 
} 

function randrange ( lower, upperbound ) {
	// Finds a random integer from 'lower' to 'upperbound-1'
	return Math.floor( Math.random() * upperbound + lower );
}

// We want to be able to alias the order of stimuli to a single number which
// can be stored and which can easily replicate a given stimulus order.
function changeorder( arr, ordernum ) {
	var thisorder = ordernum;
	var shufflelocations = new Array();
	for (var i=0; i<arr.length; i++) {
		shufflelocations.push(i);
	}
	for (i=arr.length-1; i>=0; --i) {
		var loci = shufflelocations[i];
		var locj = shufflelocations[thisorder%(i+1)];
		thisorder = Math.floor(thisorder/(i+1));
		var tempi = arr[loci];
		var tempj = arr[locj];
		arr[loci] = tempj;
		arr[locj] = tempi;
	}
	return arr;
}

// Fisher-Yates shuffle algorithm.
// modified from http://sedition.com/perl/javascript-fy.html
function shuffle( arr, exceptions ) {
	var i;
	exceptions = exceptions || [];
	var shufflelocations = new Array();
	for (i=0; i<arr.length; i++) {
		if (exceptions.indexOf(i)==-1) { shufflelocations.push(i); }
	}
	for (i=shufflelocations.length-1; i>=0; --i) {
		var loci = shufflelocations[i];
		var locj = shufflelocations[randrange(0, i+1)];
		var tempi = arr[loci];
		var tempj = arr[locj];
		arr[loci] = tempj;
		arr[locj] = tempi;
	}
	return arr;
}

// This function swaps two array members at random, provided they are not in
// the exceptions list.
function swap( arr, exceptions ) {
	var i;
	var except = exceptions ? exceptions : [];
	var shufflelocations = new Array();
    for (i=0; i<arr.length; i++) {
        if (except.indexOf(i)==-1) { shufflelocations.push(i); }
    }
    
    for (i=shufflelocations.length-1; i>=0; --i) {
        var loci = shufflelocations[i];
        var locj = shufflelocations[randrange(0,i+1)];
        var tempi = arr[loci];
        var tempj = arr[locj];
    	arr[loci] = tempj;
    	arr[locj] = tempi;
    }
    
	return arr;
}


// Mean of booleans (true==1; false==0)
function boolpercent(arr) {
	var count = 0;
	for (var i=0; i<arr.length; i++) {
		if (arr[i]) { count++; } 
	}
	return 100* count / arr.length;
}

// View functions
function appendtobody( tag, id, contents ) {
	var el = document.createElement( tag );
	el.id = id;
	el.innerHTML = contents;
	return el;
}

// Gets a path string describing a line in Raphael.
function raphael_line( x1, y1, x2, y2 ) {
	pathstring = Raphael.format( "M{0},{1}L{2},{3}", x1, y1, x2, y2 );
	return pathstring;
}


// Data submission
// NOTE: Ended up not using this.
function posterror() { alert( "There was an error. TODO: Prompt to resubmit here." ); }
function submitdata() {
	$.ajax("submit", {
			type: "POST",
			async: false,
			data: {datastring: datastring},
			// dataType: 'text',
			success: thanks,
			error: posterror
	});
}


/********************
* TASK-GENERAL CODE *
********************/

// Globals defined initially.

// Stimulus info
var tvImages = {
	broken: "static/images/tvnan.png",
	ch1: "static/images/tvch1.png",
	ch2: "static/images/tvch2.png" 
};

// TV Stim variables
var maxantlength = 300, extrastem = 10,
    tvwidth=123, tvheight=100,
    tvcanvaswidth = Math.max( maxantlength, tvwidth ),
    tvcanvasheight = maxantlength + tvheight + extrastem,
    tvx=(tvwidth >= maxantlength ? 0 : (maxantlength-tvwidth)/2 ), tvy=tvcanvasheight - tvheight, 
    stemlength = (maxantlength / 2)+extrastem,
    stemx = tvx + (tvwidth/2), 
    stemy1 = tvy, stemy2 = tvy - stemlength;

// Timin gvariables
var prequerytime = 500; // Time after stim goes on, before query buttons go on.
var acknowledgmenttime = 500; // Time after response before stim goes off
var isi = 500; // ISI


// Task objects
var testobject;


// Mutable global variables
var responsedata = [],
    currenttrial = 1,
    datastring = "",
    lastperfect = false;

// Data handling functions
function recordinstructtrial (instructname, rt ) {
	trialvals = subjinfo +  ["INSTRUCT", instructname, rt];
	datastring = datastring.concat( trialvals, "\n" );
}
function recordtesttrial (word, color, trialtype, resp, hit, rt ) {
	trialvals = subjinfo +  [currenttrial,  "TEST", word, color, hit, resp, hit, rt];
	datastring = datastring.concat( trialvals, "\n" );
	currenttrial++;
}

/********************
* HTML snippets
********************/
var pages = {};

var showpage = function(pagename) {
	$('body').html( pages[pagename] );
};

var pagenames = [
	"postquestionnaire",
	"test",
	"instruct"
];


/********************
* Experiment block object
********************/
var currentBlock;

function ExperimentBlock() { }

// Mutable variables
ExperimentBlock.prototype.trialnum = 0;
ExperimentBlock.prototype.blocknum = 0;

// Some imporant variables.
ExperimentBlock.prototype.tvcanvas = Raphael(document.getElementById("stim"), tvcanvaswidth, tvcanvasheight );
ExperimentBlock.prototype.acknowledgment = '<p>Thanks for your response!</p>';
ExperimentBlock.prototype.textprompt = '<p id="prompt">Which channel do you think this TV picks up?</p>';

// Stimulus drawing methods:
ExperimentBlock.prototype.draw_tv = function(length, angle, channel) {
	// TV params
	var angle_radiens = (angle / 180) * Math.PI,
	    xdelta = length * Math.cos( angle_radiens ),
	    ydelta = length * Math.sin( angle_radiens );
	
	var strokewidth = 3,
	    antenna_attr = {"stroke-width": strokewidth},
	    stem_attr = {"stroke-width": strokewidth,
	                 "stroke": "#999"};
	
	var stem = this.tvcanvas.
		path(this.raphael_line(stemx, stemy1, stemx, stemy2)).
		attr(stem_attr);
	var antenna = this.tvcanvas.
		path(this.raphael_line(stemx-xdelta, stemy2-ydelta,
	                        stemx+xdelta, stemy2+ydelta)).
		attr(antenna_attr);
	var tv = this.tvcanvas.image(tvImages[channel], tvx, tvy, tvwidth, tvheight);
};
ExperimentBlock.prototype.clearTV = function() { this.tvcanvas.clear(); };

// Methods for doing a trial.
ExperimentBlock.prototype.addbuttons = function(callback) {
	$('#query').html( buttons );
	$('input').click( callback );
	$('#query').show();
};
ExperimentBlock.prototype.addprompt = function() {
	$('#query').html( textprompt ).show();
};
ExperimentBlock.prototype.dotrial = function(stim) {
	draw_tv( maxantlength/2, 100, "broken" );
	// stimon = new Date().getTime();
	setTimeout(
		function(){
			lock=false;
			var buttonson = new Date().getTime();
			addbuttons(function() {
				var resp = this.value;
				var rt = (new Date().getTime()) - buttonson;
				this.recordQueryTrial(stim, resp, rt);
				$('#query').html( this.acknowledgment );
				// Wait acknowledgmenttime to clear screen
				setTimeout(
					function() {
						$('#query').html('');
						this.clearTV();
						// Wait ISI to go to next trial.
						setTimeout( this.nexttrial, isi );
					},
					acknowledgmenttime);
			});
		},
		prequerytime);
};

ExperimentBlock.prototype.recordtrial = function(stim, resp, rt ) {
	trialvals = subjinfo +  [this.trialnum, this.blocknum] + stim + [resp, rt];
	datastring = datastring.concat( trialvals, "\n" );
	currenttrial++;
};

ExperimentBlock.prototype.nexttrial = function() {
	if (! this.items.length) {
		finishblock();
	}
	else {
		ExperimentBlock.prototype.trialnum += 1;
		var stim = stims.pop();
		this.dotrial( stim );
	}
};

ExperimentBlock.prototype.beginblock = function() { 
	this.nexttrial(); 
};
ExperimentBlock.prototype.finishblock = function() { };

/************************
* INSTRUCTIONS OBJECT   *
************************/
function InstructBlock() {
	ExperimentBlock.call(this); // Call parent constructor
}

TestPhase.prototype = new ExperimentBlock(instructionscreens);
TestPhase.prototype.constructor = TestPhase;

InstructBlock.prototype.items = [
	"instruct1",
	"instructFinal"
];

// Show an instruction screen.
InstructBlock.prototype.dotrial = function(stim) {
    if (this.items.length === 0) {
        this.finishblock();
        return false;
    }
    var that = this,
        currentscreen = screens.splice(0, 1)[0];
    showpage( currentscreen );
    var timestamp = new Date().getTime();
    $('.continue').click( function() {
        that.recordtrial();
        that.dotrial();
    });
    return true;
};

// Flow control:
InstructBlock.prototype.finishblock = function() {
    // TODO: maybe add instruction quiz.
	test = new TestPhase();
	test.beginblock();
};

// Record
InstructBlock.prototype.recordtrial = function(currentscreen, rt) {
	recordinstructtrial( currentscreen, rt );
	trialvals = subjinfo + ["INSTRUCT", stim, rt];
	datastring = datastring.concat( trialvals, "\n" );
};


/********************
* CODE FOR TEST     *
********************/

function TestBlock() {
	ExperimentBlock.call(this); // Call parent constructor
}

TestPhase.prototype = new ExperimentBlock();
TestPhase.prototype.constructor = TestBlock;

	
	
/*************
* Finish up  *
*************/
var givequestionnaire = function() {
	var timestamp = new Date().getTime();
	showpage('postquestionnaire');
	recordinstructtrial( "postquestionnaire", (new Date().getTime())-timestamp );
	$("#continue").click(function () {
		finish();
		submitquestionnaire();
	});
	// $('#continue').click( function(){ trainobject = new TrainingPhase(); } );
	// postback();
};
var submitquestionnaire = function() {
	$('textarea').each( function(i, val) {
		datastring = datastring.concat( "\n", this.id, ":",  this.value);
	});
	$('select').each( function(i, val) {
		datastring = datastring.concat( "\n", this.id, ":",  this.value);
	});
	insert_hidden_into_form(0, "subjid", subjid );
	insert_hidden_into_form(0, "data", datastring );
	$('form').submit();
};

var startTask = function () {
	// Provide opt-out 
	window.onbeforeunload = function(){
    	$.ajax("quitter", {
    			type: "POST",
    			async: false,
    			data: {subjId: subjid, dataString: datastring}
    	});
		alert( "By leaving this page, you opt out of the experiment.  You are forfitting your $1.00 payment and your 1/10 chance to with $10. Please confirm that this is what you meant to do." );
		return "Are you sure you want to leave the experiment?";
	};
};

var finish = function () {
	window.onbeforeunload = function(){ };
};

// vi: et! ts=4 sw=4
