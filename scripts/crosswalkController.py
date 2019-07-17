#!/usr/bin/env python
import rospy
import numpy as np
from utils import *
from genesis_path_follower.msg import plotting_state
from genesis_path_follower.msg import ped_state
from genesis_path_follower.msg import vehicle_state
from std_msgs.msg import Float32

#Takes in LIDAR position of pedestrian and runs crosswalk controller code
class CrosswalkController():

	def __init__(self):
		rospy.init_node('crosswalk_controller', anonymous = True)
		rospy.Subscriber('vehicle_state',vehicle_state, self.parseVehicleState, queue_size = 2)
		rospy.Subscriber("/ped_state",ped_state, self.parsePedestrianState, queue_size = 2)
		self.plot_pub  = rospy.Publisher("/vehicle/plotting_state",plotting_state,queue_size = 1)
		self.accel_pub = rospy.Publisher("/control/accel", Float32, queue_size =2)

		self.rate = rospy.get_param('rate')
		self.r = rospy.Rate(self.rate)

		#road parameters
		self.roadFraction = rospy.get_param('roadFraction') #defines position of crosswalk
		self.roadLength   = rospy.get_param('roadLength')   #meters
		self.v0           = rospy.get_param('v0')           #m/s, desired speed of vehicle
		self.dt           = rospy.get_param('dt')
		self.numDelayedSamples= rospy.get_param('actuatorDelay') #number of timesteps
		self.carLane      = rospy.get_param('carLane')

		if self.numDelayedSamples == 0:
			pass
		else:
			self.delayedInputVector = np.zeros(self.numDelayedSamples)

		#initialize objects
		self.road = Road(length = self.roadLength)
		self.crosswalk = Crosswalk(self.road, roadFraction = self.roadFraction) 	
		self.sidewalk  = Sidewalk(self.road) 
		self.veh = Vehicle(crosswalk = self.crosswalk, sidewalk = self.sidewalk, road = self.road, v0 = self.v0, lane = self.carLane)
		self.vehicleX = self.veh.lane * self.road.laneWidth + self.road.laneWidth / 2 - self.veh.width/2 #x position of vehicle - assumed constant

		#initialize variables for controller
		self.xV = 0. #ego vehicle position, meters
		self.dxV = self.v0 #ego vehicle velocity, meters / second

		self.xP = 0.
		self.dxP = 0. 
		self.posY = 0. #Y position of pedestrian
		self.time = 0.0
		self.pedStart = "right"

		#initialize acceleration to send to vehicle
		self.currAx_mps2 = 0. #commanded accel
		self.pub_loop()

	def parsePedestrianState(self, msg):
		self.xP = self.vehicleX + msg.posX
		self.dxP = msg.velX
		self.posY = msg.posY

	def parseVehicleState(self, msg):
		self.xV = msg.xV
		self.dxV = msg.dxV

	def getAccel(self):
		self.currAx_mps2,_,_     = self.veh.getAccel(self.xP, self.dxP, self.xV, self.dxV, 0, self.pedStart)

		commandedAccel = self.currAx_mps2
		self.accel_pub.publish(commandedAccel)

		#update variables to publish to policy server. Note that prevAccel is updated in subscriber callback function
		self.time += self.dt

	def pub_loop(self):
		#Start testing!
		t_start = rospy.Time.now()

		while not rospy.is_shutdown():
			t_now = rospy.Time.now()
			dt = t_now - t_start
			dt_secs = dt.secs + 1e-9 * dt.nsecs

			plot_state = plotting_state()
			plot_state.header.stamp = rospy.Time.now()

			self.getAccel()

			plot_state.xP = self.xP
			plot_state.xV = self.xV
			plot_state.ddxV = self.currAx_mps2
			plot_state.yP = self.xV + self.posY

			self.plot_pub.publish(plot_state)
			self.r.sleep()


if __name__=="__main__":
	print 'Starting Simulation.'
	try:
		cc = CrosswalkController()
	except rospy.ROSInterruptException:
		pass # to handle node shutdown cleanly