import cv2
import numpy as np
from perception_functions import get_BB_img_point
from PIL import Image


def trasform_img_cones_to_xyz(img_cones,width, height, depth_type, img_depth, h_fov, v_fov, camera_pos):
    '''
    Get multiple BB in image plain (img_cones) and transform it to xyz coordinates of cognata car (xyz_cones)
    :param img_cones:
    :param width: image width
    :param height: image height
    :param depth_type: uint16 / float32
    :param img_depth: depth image
    :param h_fov: horizontal field of view
    :param v_fov: vertical field of view
    :param camera_pos: camera position in cognata car coordinate system
    :return: list of (X,Y,Z,type) in cognata car coordinate system (X -forward, Y-left, Z-upward)
    '''

    # Extract parameters
    K, R_inv, t_inv, cx, cy, f = extract_parameters_to_xyz_from_uvd(width, height, h_fov, camera_pos)

    # Translating depth image from bytes to pixel array
    depth_arr = np.asarray(Image.frombytes("I;16", (width, height), img_depth))

    # Choose single representative point in each BB:
    img_cone_points = []  # list of (x,y,type) BB representative point in img plain
    for img_cone in img_cones:
        img_cone_points.append(get_BB_img_point(img_cone)) # Get the u,v of center of BB, and type
    img_cone_points = np.asarray(img_cone_points)

    # Preparing indices and appropriate depths values
    index_x = img_cone_points[:, 0].astype(np.int)
    index_y = img_cone_points[:, 1].astype(np.int)
    depths = depth_arr[index_y, index_x]  # Using Matrix mult instead of loop to increase performance
    depths = depths/100  # convert from [cm] to [m]
    depths = convert_radial_to_perpendicular_depth(img_cone_points[:,0:2], depths, cx, cy, f)

    # Extract xyz coordinates of each cone together using matrices
    positions = world_XYZ_from_uvd(img_cone_points[:,0:2], depths=depths, K=K, R_inv=R_inv,
                                   t_inv=t_inv)

    # Arrange the data (need to be upgrade to more compact way with no for loop)
    xyz_cones = []  # list of (X,Y,Z,type) in ENU coordinate system (X - right, Y-forward, Z-upward)
    for index, img_cone_point in enumerate(img_cone_points):
        # img_depth_px = img_depth.load()
        xyz_cones.append(list(positions[index,:]))
        # insert cone type to xyz_cones:
        xyz_cones[-1].append(img_cone_point[-1])

    return xyz_cones

def extract_parameters_to_xyz_from_uvd(width, height, h_fov, camera_pos):

    # Focal length of the camera
    h_fov = h_fov*np.pi / 180 # in [rad]
    f = width / (2 * np.tan(h_fov / 2)) # 1/2w        (hFOV)
                                        # ----  = tan (----)
                                        #  f          (  2 )
    # Camera pin hole position on image
    cx = width / 2
    cy = height / 2 - 3  # horizon is 3 pixels above the centerline

    # Camera matrix
    K = np.array([[f, 0, cx],
                  [0, f, cy],
                  [0, 0, 1]], dtype=np.float)

    # Transformation from camera -> cognata car coordinate system
    angle = - np.pi / 2.0

    #  Transformation from default camera cord. system (z front, x right, y down) to ENU
    R_ENU = np.array([[1, 0, 0],
                     [0, np.cos(angle), -np.sin(angle)],
                     [0, np.sin(angle), np.cos(angle)]], dtype=np.float)

    #  Transformation from ENU to Cognata (Car) cord system (z up,x front,y left)- get from message: camera rot              
    R_ENU2cognata = np.array([[0, 1, 0],
                              [-1, 0, 0],
                              [0, 0, 1]], dtype=np.float)

    # In the future we will get from Cognata the R matrix, need to check what we get.                           
    R_inv = R_ENU2cognata@R_ENU

    # Camera position in cognata car coordinate system
    t_inv = np.array([camera_pos.x,camera_pos.y,camera_pos.z] , dtype=np.float)

    return K, R_inv, t_inv, cx, cy, f

def trasform_img_point_to_xyz(img_point, img_depth, h_fov, v_fov, width, height):
    # extract parameters
    u = img_point[0]
    v = img_point[1]
    alpha_h = (180 - h_fov)/2  # [deg]
    alpha_v = (180 - v_fov)/2  # [deg]
    # calculating gammas:
    gamma_h = alpha_h + (1-u / width) * h_fov  # [deg]
    gamma_v = alpha_v + (v / height) * v_fov  # [deg]
    # calculating X,Y,Z in ENU coordinate system (X - right, Y-forward, Z-upward)
    Y = img_depth
    X = img_depth / np.tan(gamma_h * np.pi / 180)
    Z = img_depth / np.tan(gamma_v * np.pi / 180)

    return [X, Y, Z]

def inverse_perspective(R, t):
    Ri = np.transpose(R)  # for a rotation matrix, inverse is the transpose
    ti = -Ri @ t
    return Ri, ti

def convert_radial_to_perpendicular_depth(points, depths, cx, cy, f):
    '''
    converts radial depth to perpendicular depth in image plain
    :param points: array of points in the image 2D plain
    :param depths: appropriate radial depth values for each point in points
    :param cx: image principal  point horizontal pixel index
    :param cy: image principal point vertial pixel index
    :param f: camera focal length
    :return: corresponding perpendicular depth values
    '''
    return depths*f/(f**2 + (points[:, 0]-cx)**2 + (points[:, 1]-cy)**2)**0.5

def compare_XYZ_to_GT (xyz_cones, xyz_cones_GT):
    '''
    get list of xyz detections and list of ground truth xyz and return index array of couples
    connecting between the detected xyz and the closest ground truth xyz
    :param xyz_cones:
    :param xyz_cones_GT:
    :return: indices array: corresponding closest indices in GT array for each of the xyz detections
    '''
    indices = [0]*len(xyz_cones)
    for i, xyz_cone in enumerate(xyz_cones):
        min_index, min_dist = 0, 0
        for i_GT, xyz_cone_GT in enumerate(xyz_cones_GT):
            dX = xyz_cone[0]-xyz_cone_GT[0]
            dY = xyz_cone[1] - xyz_cone_GT[1]
            dZ = xyz_cone[2] - xyz_cone_GT[2]
            dist = (dX**2+dY**2+dZ**2)**0.5
            if dist < min_dist or i_GT == 0:
                min_dist = dist
                min_index = i_GT
        indices[i] = min_index

    return indices

def world_XYZ_from_uvd(points, depths, K, R_inv, t_inv):
    '''
    Transformingu uvd (uv in 2D image plain + depth) to xyz in world coordinates using matrices
    :param points: array of points in the image 2D plain
    :param depths: appropriate perpendicular depth values for each point in points
    :param K: camera matrix
    :param Rinv: transformation from camera coordinate system to world coordinate system
    :param tinv: camera position in world coordinates
    :return: position of requested points in world coordinates
    '''
    K_inv = np.linalg.inv(K)
    uv1 = cv2.convertPointsToHomogeneous(points)[:,0,:]
    # s(u,v,1) = K(R(xyz)+t)
    # xyz = Rinv*(Kinv*s*(uv1)) + tinv
    image_vectors = np.multiply(uv1.T, [depths]) # depths is broadcast over the 3 rows of uv.T
    positions = (R_inv@K_inv@image_vectors).T + t_inv  # tinv automatically broadcast to all matrix rows

    return positions

