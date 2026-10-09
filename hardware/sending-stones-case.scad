// Sending Stones Model Railroad Layout
// ------------------------------------
// Abraxas3d
// units are in mm


// ------------------------------------
// Parameters
// ------------------------------------

//make curves nice
$fn = 64;

// base layer dimensions
base_width = 700;
base_depth = 200;
base_height = 6.25; // quarter inch acrylic sheet

// X728 box dimensions (approximate)
x728_width = 122;
x728_depth = 92;
x728_height = 60;
    
// Ground plane and donut stand dimensions
ground_plane_radius = 100; //~quarter wave ground plane
ground_plane_height = 1; // 1 mm aluminum plate
donut_height = 2*24.5; //one inch height increments
donut_radius = 24.5; //one inch radius
donut_hole_radius = 8; // 16 mm clearance for SMA bulkhead connector in donut
sma_hole_radius = 6.5/2; // 6.5 mm hole for SMA connector

// Heltec v3 case dimensions
heltec_width = 56;
heltec_depth = 30;
heltec_height = 11;
heltec_wall = 2;
usb_width = 9.5;
usb_height = 4;
usb_sill = 5;

// ------------------------------------
// Components Defined
// ------------------------------------

// the base layer
cube([base_width, base_depth , base_height], center = true);

// X728
translate([0, -base_depth/6, base_height/2 + x728_height/2])
    {
    cube([x728_width, x728_depth, x728_height], center = true);
    };

// Ground plane donut hole mounts with cable cutout
translate([-250, 0, base_height/2 + donut_height/2])
    {
    difference()
        {
        cylinder(donut_height, donut_radius, donut_radius, center = true); //donut
        cylinder(donut_height, donut_hole_radius, donut_hole_radius, center = true); //hole
        translate([donut_radius/2, 0, 0])
            {
            cube([donut_radius, donut_hole_radius*2, donut_height], center = true); //channel out
            };
        };
    };
    
translate([250, 0, base_height/2 + donut_height/2])
    {
    difference()
        {
        cylinder(donut_height, donut_radius, donut_radius, center = true);
        cylinder(donut_height, donut_hole_radius, donut_hole_radius, center = true);
        translate([-donut_radius/2, 0, 0])
            {
            cube([donut_radius, donut_hole_radius*2, donut_height], center = true);
            };
        };
    };

// Ground planes with SMA bulkhead holes
translate([-250, 0, base_height/2 + donut_height + ground_plane_height/2])
    {
   difference()
        {
        cylinder(ground_plane_height, ground_plane_radius, ground_plane_radius, center = true);
        cylinder(ground_plane_height, sma_hole_radius, sma_hole_radius, center = true);
        };
    };
    
translate([250, 0, base_height/2 + donut_height + ground_plane_height/2])
    {
    difference()
        {
        cylinder(ground_plane_height, ground_plane_radius, ground_plane_radius, center = true);
        cylinder(ground_plane_height, sma_hole_radius, sma_hole_radius, center = true);
        }
    };

// Heltec v3 holders

translate([-120, base_depth/4, base_height/2])
    {
    cube([heltec_width, heltec_depth, heltec_wall], center = true); //base
    }


translate([-120, base_depth/4, base_height/2 + heltec_height/2])
    {
    difference()
        {
        cube([heltec_width, heltec_depth, heltec_height], center = true); // case
        cube([heltec_width - 2*heltec_wall, heltec_depth - 2*heltec_wall, heltec_height], center = true); // interior case
        
        //translate([0,0,-(heltec_height/2) + heltec_wall + usb_sill])
        translate([0,0,-(heltec_height/2) + heltec_wall + usb_sill + usb_height/2])
        {
        cube([heltec_width + 4*heltec_wall, usb_width, 2*usb_height], center = true); // holes
        }
        }
    };
 

translate([120, base_depth/4, base_height/2])
    {
    cube([heltec_width, heltec_depth, heltec_wall], center = true); //base
    }


translate([120, base_depth/4, base_height/2 + heltec_height/2])
    {
    difference()
        {
        cube([heltec_width, heltec_depth, heltec_height], center = true); // case
        cube([heltec_width - 2*heltec_wall, heltec_depth - 2*heltec_wall, heltec_height], center = true); // interior case
        
        translate([0,0,-(heltec_height/2) + heltec_wall + usb_sill + usb_height/2])
        {
        cube([heltec_width + 4*heltec_wall, usb_width, 2*usb_height], center = true); // holes
        }
        }
    };