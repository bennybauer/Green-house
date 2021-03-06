﻿import os
import pandas as pd
import numpy as np
import spectral.io.envi as envi
# import matplotlib.pyplot as plt
#import spectral
import skimage.draw 
import time as timeit
import glob
from skimage import filters


def cut_images_in_fldr(DARK,ROI,IMAGE1):
    print ( DARK)
    
    print ( ROI)
    
    print ( IMAGE1)
    ROI_src = ROI
    dark_path = DARK
    cal_path = r'C:\Users\tonish\Desktop\Chamama\Radiometric_1x1.hdr'
    image_path = IMAGE1

	# initialize empty arrays
    data = []
#    df_list = []
    sheet_names = []

	# read the TXT ROI file
    with open(ROI_src) as f:
#        col_names = []
        data = []
        content = f.readlines()
        for i in content:
            if "ROI name" in i:
                sheet_names.append(i.split(":")[1].strip())
            else:
                row = " ".join(i.split())
                data.append(row.split(" "))


	# this list must comply with the same roi features in the file
    group_lines = ['spectralon','v1','v2','v3','h0','h1','h2','h3','h4','h5','h6','h7','h8','h9','h10','h11','h12','h13','h14','h15','h16','h17','h18','Black1','Black2']

	# turn the ROI file to a DF
    df = pd.DataFrame(data,dtype = int)
    first_row = df.loc[df[1]=='ID'].index[0]
    df = df.loc[first_row:,:]
    df.columns = df.iloc[0]
    df = df.iloc[1:,:]
    df.fillna(value=np.nan, inplace=True)
    df = df.iloc[:,1:-5]
    col_list = df.columns.tolist()
    col_list = col_list[1:3]
    wv_list = ['B1','B2','B3']
    new_col_list = col_list+wv_list
    df.columns = new_col_list
    df['group_id'] = df.isnull().all(axis=1).cumsum() #give id to a group, a group is seperated by "nan" row
    df = df.dropna()
    for i in df['group_id'].unique():
        df.loc[:,'group_id'][df['group_id'] ==i] = group_lines[i]
        df['X'] = df['X'].astype('int32')
        df['Y'] = df['Y'].astype('int32')
        df['coor'] = list(zip(df.X, df.Y))
	# df[df['group_io'] ==i] = group_id[i]
#    df_list = [x for _, x in df.groupby(df['group_id'])]
	# df = df.iloc[:,:-1]

	# calibrate the imgae
    image = envi.open(image_path).load().load()
    cal_img = envi.open(cal_path,image = cal_path[:-3] + 'cal').load()
    dark_img = envi.open(dark_path).load().mean(axis=0)

	# Radiance = RadCalCoefficient * (data – dark)  / tint_data

	# get the integration time
    time_integration = float(image.metadata['tint'][:2])
    rad_image = np.empty_like(image)
    for i in range(image.shape[0]):
        rad_image[i] =  np.divide(np.multiply(np.subtract(image[i] , dark_img), cal_img),time_integration)

	# calculate reflectance
	# white panel position
    ref_x_start = int(df[df['group_id']=='spectralon']['X'].astype(int).min())
    ref_x_stop = int(df[df['group_id']=='spectralon']['X'].astype(int).max())
    ref_y_start = int(df[df['group_id']=='spectralon']['Y'].astype(int).min())
    ref_y_stop = int(df[df['group_id']=='spectralon']['Y'].astype(int).max())
	# white panel mean spectrum
    spectralon = rad_image[ref_y_start:ref_y_stop,ref_x_start:ref_x_stop]
    spectralon_avg = spectralon.mean(axis=(0,1))
	# black panel position
    black_x_start = int(df[df['group_id']=='Black1']['X'].astype(int).min())
    black_x_stop = int(df[df['group_id']=='Black1']['X'].astype(int).max())
    black_y_start = int(df[df['group_id']=='Black1']['Y'].astype(int).min())
    black_y_stop = int(df[df['group_id']=='Black1']['Y'].astype(int).max())
	# black panel mean spectrum
    black = rad_image[black_y_start:black_y_stop,black_x_start:black_x_stop]
    black_avg = black.mean(axis=(0,1))

    refle_img = np.divide((np.subtract(rad_image,black_avg)), (np.subtract(spectralon_avg, black_avg)))
    red = refle_img[:,:,210]
    red_wave = float(image.metadata['wavelength'][210])
    nir = refle_img[:,:,266]
    nir_wave = float(image.metadata['wavelength'][266])
	#NDVI = np.divide(np.subtract(nir, red),np.add(nir, red))
    DIFF = np.subtract(nir, red)/(nir_wave-red_wave)
    """
    trying to cut the images differently
    """

    # slice the  image to individual plants
    first_column = {}
    second_column = {}
    third_column = {}
    forth_column = {}

    hor_lines = ['h0', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'h7', 'h8', 'h9', 'h10', 'h11', 'h12', 'h13', 'h14', 'h15',
				 'h16', 'h17', 'h18']
    ver_lines = ['v1', 'v2', 'v3']


    def create_poly_1st_col(rr):
        x_mina = df[df['group_id'] == hor_lines[rr]]['X'].min() #upper line first x
        x_mina2 = df[df['group_id'] == hor_lines[rr]][df['X'] == x_mina]['Y'].values[0] #upper line first y
        X_minb = df[df['group_id'] == hor_lines[rr + 1]]['X'].min() #lower line first x
        x_minb2 = df[df['group_id'] == hor_lines[rr + 1]][df['X'] == X_minb]['Y'].values[0] #lower line first y
        left_vertical = np.array([[0, i] for i in range(x_mina2, x_minb2 + 1)])[1:-1]

        a = np.intersect1d(df[df['group_id'] == hor_lines[rr]]['coor'], df[df['group_id'] == ver_lines[0]]['coor'])[0][0] #intersection of upperline and v1 x
        c = df[df['group_id'] == hor_lines[rr]]['coor'][::-1] # upper line
        top_horizontal = np.array([[i, c.iloc[i][1]] for i in range(a + 1)])
		
        
        b = df[df['group_id'] == hor_lines[rr + 1]]['coor'][::-1] # lower line
        c = np.intersect1d(df[df['group_id'] == hor_lines[rr + 1]]['coor'], df[df['group_id'] == ver_lines[0]]['coor']) # intersection of lowerlnie and v1
        bottom_horizontal = np.array([[i, b.iloc[i][1]-1] for i in range(c[0][0] + 1)])
		
        a = df[df['group_id'] == ver_lines[0]]
        b = np.intersect1d(df[df['group_id'] == hor_lines[rr]]['coor'], df[df['group_id'] == ver_lines[0]]['coor'])
        c = np.intersect1d(df[df['group_id'] == hor_lines[rr + 1]]['coor'], df[df['group_id'] == ver_lines[0]]['coor'])
        right_vertical = np.array([[a[a['Y'] == i]['X'].values[0], i] for i in range(b[0][1], c[0][1])])[1:]

        poly = np.concatenate((top_horizontal, left_vertical, bottom_horizontal, right_vertical))
        poly = poly[poly[:, 0].argsort()]
        poly1 = skimage.draw.polygon_perimeter(poly[:, 0], poly[:, 1])
        return poly1


    def create_poly_2nd_col(rr):
        a = df[df['group_id'] == ver_lines[0]]
        b = np.intersect1d(df[df['group_id'] == hor_lines[rr]]['coor'], df[df['group_id'] == ver_lines[0]]['coor'])
        c = np.intersect1d(df[df['group_id'] == hor_lines[rr + 1]]['coor'], df[df['group_id'] == ver_lines[0]]['coor'])
        left_vertical = np.array([[a[a['Y'] == i]['X'].values[0], i] for i in range(b[0][1], c[0][1])])[1:]

        a = np.intersect1d(df[df['group_id'] == hor_lines[rr]]['coor'], df[df['group_id'] == ver_lines[0]]['coor'])[0][0]
        b = df[df['group_id'] == hor_lines[rr]]
        d = np.intersect1d(df[df['group_id'] == hor_lines[rr]]['coor'], df[df['group_id'] == ver_lines[1]]['coor'])[0][0]
        top_horizontal = np.array([[i, b[b['X'] == i]['Y'].values[0]] for i in range(a, d)])
		# top_horizontal = np.array([[0,df[df['group_id'] == 'h0']['Y'][::-1].iloc[0]]] + tmp_list)

        a = np.intersect1d(df[df['group_id'] == hor_lines[rr + 1]]['coor'], df[df['group_id'] == ver_lines[0]]['coor'])[0][
			0]
        b = df[df['group_id'] == hor_lines[rr + 1]]
		#     c = df[df['group_id'] == hor_lines[rr]][::-1]
        d = np.intersect1d(df[df['group_id'] == hor_lines[rr + 1]]['coor'], df[df['group_id'] == ver_lines[1]]['coor'])[0][
			0]
        bottom_horizontal = np.array([[i, b[b['X'] == i]['Y'].values[0]] for i in range(a, d)])
		# bottom_horizontal = np.array([[0,df[df['group_id'] == 'h1']['Y'][::-1].iloc[0]]] + tmp_list)

        a = df[df['group_id'] == ver_lines[1]]
        b = np.intersect1d(df[df['group_id'] == hor_lines[rr]]['coor'], df[df['group_id'] == ver_lines[1]]['coor'])
        c = np.intersect1d(df[df['group_id'] == hor_lines[rr + 1]]['coor'], df[df['group_id'] == ver_lines[1]]['coor'])
        right_vertical = np.array([[a[a['Y'] == i]['X'].values[0], i] for i in range(b[0][1], c[0][1])])[1:]
		# right_vertical = [tuple(int(i) for i in np.intersect1d(df[df['group_id'] == 'h0']['coor'],df[df['group_id'] == 'v1']['coor'])[0])]
		# poly = np.array(bottom_horizontal)
        poly = np.concatenate((top_horizontal, left_vertical, bottom_horizontal, right_vertical))
        poly = poly[poly[:, 0].argsort()]
        poly1 = skimage.draw.polygon_perimeter(poly[:, 0], poly[:, 1])
        return poly1


    def create_poly_3rd_col(rr):
        a = df[df['group_id'] == ver_lines[1]]
        b = np.intersect1d(df[df['group_id'] == hor_lines[rr]]['coor'], df[df['group_id'] == ver_lines[1]]['coor'])
        c = np.intersect1d(df[df['group_id'] == hor_lines[rr + 1]]['coor'], df[df['group_id'] == ver_lines[1]]['coor'])
        left_vertical = np.array([[a[a['Y'] == i]['X'].values[0], i-1] for i in range(b[0][1], c[0][1])])[1:]

        a = np.intersect1d(df[df['group_id'] == hor_lines[rr]]['coor'], df[df['group_id'] == ver_lines[1]]['coor'])[0][0]
        b = df[df['group_id'] == hor_lines[rr]]
        d = np.intersect1d(df[df['group_id'] == hor_lines[rr]]['coor'], df[df['group_id'] == ver_lines[2]]['coor'])[0][0]
        top_horizontal = np.array([[i, b[b['X'] == i]['Y'].values[0]] for i in range(a, d)])
		# top_horizontal = np.array([[0,df[df['group_id'] == 'h0']['Y'][::-1].iloc[0]]] + tmp_list)

        a = np.intersect1d(df[df['group_id'] == hor_lines[rr + 1]]['coor'], df[df['group_id'] == ver_lines[1]]['coor'])[0][
			0]
        b = df[df['group_id'] == hor_lines[rr + 1]]
		#     c = df[df['group_id'] == hor_lines[rr]][::-1]
        d = np.intersect1d(df[df['group_id'] == hor_lines[rr + 1]]['coor'], df[df['group_id'] == ver_lines[2]]['coor'])[0][
			0]
        bottom_horizontal = np.array([[i, b[b['X'] == i]['Y'].values[0]-1] for i in range(a, d)])
		# bottom_horizontal = np.array([[0,df[df['group_id'] == 'h1']['Y'][::-1].iloc[0]]] + tmp_list)

        a = df[df['group_id'] == ver_lines[2]]
        b = np.intersect1d(df[df['group_id'] == hor_lines[rr]]['coor'], df[df['group_id'] == ver_lines[2]]['coor'])
        c = np.intersect1d(df[df['group_id'] == hor_lines[rr + 1]]['coor'], df[df['group_id'] == ver_lines[2]]['coor'])
        right_vertical = np.array([[a[a['Y'] == i]['X'].values[0], i-1] for i in range(b[0][1], c[0][1])])[1:]
		# right_vertical = [tuple(int(i) for i in np.intersect1d(df[df['group_id'] == 'h0']['coor'],df[df['group_id'] == 'v1']['coor'])[0])]
		# poly = np.array(bottom_horizontal)
        poly = np.concatenate((top_horizontal, left_vertical, bottom_horizontal, right_vertical))
        poly = poly[poly[:, 0].argsort()]
        poly1 = skimage.draw.polygon_perimeter(poly[:, 0], poly[:, 1])
        return poly1


    def create_poly_4th_col(rr):
		# a,b = df[df['group_id'] == 'h0']['Y'].min(),df[df['group_id'] == 'h1']['Y'].min()
    		x_mina = df[df['group_id'] == hor_lines[rr]]['X'].max()
    		x_mina2 = df[df['group_id'] == hor_lines[rr]][df['X'] == x_mina]['Y'].values[0]
    		X_minb = df[df['group_id'] == hor_lines[rr + 1]]['X'].max()
    		x_minb2 = df[df['group_id'] == hor_lines[rr + 1]][df['X'] == X_minb]['Y'].values[0]
    		right_vertical = np.array([[1023, i] for i in range(x_mina2, x_minb2 )])[1:-1]
    
    		a = np.intersect1d(df[df['group_id'] == hor_lines[rr]]['coor'], df[df['group_id'] == ver_lines[2]]['coor'])[0][0]
    		b = df[df['group_id'] == hor_lines[rr]]['X'].max()
    		c = df[df['group_id'] == hor_lines[rr]][::-1]
#    		d = np.intersect1d(df[df['group_id'] == hor_lines[rr]]['coor'], df[df['group_id'] == ver_lines[2]]['coor'])[0][1]
    		top_horizontal = np.array(
    			[[i, c[c['X'] == i]['Y'].values[0]] for i in range(a, b)] + [[i, c[c['X'] == b]['Y'].values[0]] for i in
    																		 range(b, 1024)])
    
    		a = np.intersect1d(df[df['group_id'] == hor_lines[rr + 1]]['coor'], df[df['group_id'] == ver_lines[2]]['coor'])[0][
    			0]
    		b = df[df['group_id'] == hor_lines[rr + 1]]['X'].max()
    		c = df[df['group_id'] == hor_lines[rr + 1]][::-1]
#    		d = np.intersect1d(df[df['group_id'] == hor_lines[rr + 1]]['coor'], df[df['group_id'] == ver_lines[2]]['coor'])[0][
#    			1]
    		bottom_horizontal = np.array(
    			[[i, c[c['X'] == i]['Y'].values[0]-1] for i in range(a, b)] + [[i, c[c['X'] == b]['Y'].values[0]-1] for i in
    																		 range(b, 1024)])
    
    		a = df[df['group_id'] == ver_lines[2]]
    		b = np.intersect1d(df[df['group_id'] == hor_lines[rr]]['coor'], df[df['group_id'] == ver_lines[2]]['coor'])
    		c = np.intersect1d(df[df['group_id'] == hor_lines[rr + 1]]['coor'], df[df['group_id'] == ver_lines[2]]['coor'])
    		left_vertical = np.array([[a[a['Y'] == i]['X'].values[0], i] for i in range(b[0][1], c[0][1])])[1:]
    		poly = np.concatenate((top_horizontal, left_vertical, bottom_horizontal, right_vertical))
    		poly = poly[poly[:, 0].argsort()]
    		poly1 = skimage.draw.polygon_perimeter(poly[:, 0], poly[:, 1])
    		return poly1


    for rr in range(len(hor_lines) - 1):
        print(rr)


        first_column[rr] = create_poly_1st_col(rr)
        second_column[rr] = create_poly_2nd_col(rr)
        third_column[rr] = create_poly_3rd_col(rr)
        forth_column[rr] = create_poly_4th_col(rr)

	# extract everything for first column

    first_column_names = ['1A', '2A', '3A', '4A', '5A', '6A', '7A', '8A', '9A', '10A', '11A', '12A', '13A', '14A', '15A',
						  '16A', '17A', '18A']
    forth_column_names = ['1D', '2D', '3D', '4D', '5D', '6D', '7D', '8D', '9D', '10D', '11D', '12D', '13D', '14D', '15D',
						  '16D', '17D', '18D']
    second_column_names = ['1B', '2B', '3B', '4B', '5B', '6B', '7B', '8B', '9B', '10B', '11B', '12B', '13B', '14B', '15B',
						   '16B', '17B', '18B']
    third_column_names = ['1C', '2C', '3C', '4C', '5C', '6C', '7C', '8C', '9C', '10C', '11C', '12C', '13C', '14C', '15C',
						  '16C', '17C', '18C']

	# first_column_dict = {}
	# middle_column_dict = {}
	# last_column_dict = {}

    first_keys = list(first_column.keys())
    second_keys = list(second_column.keys())
    third_keys = list(third_column.keys())
    forth_keys = list(forth_column.keys())


    def imgs2sql(rowcol, names, segmented_dict):  # rowcol = keys of segmented images, names = name of plant
        df_collector = {}

        for key1, name in zip(rowcol, names):
            print(key1, name)
            print('1', timeit.strftime("%H:%M:%S"))
			# NDVI = calculate NDVI and make next line base on it
            loop_DIFF = DIFF[segmented_dict[key1][1], segmented_dict[key1][0]]
            val = filters.threshold_otsu(loop_DIFF)
            loop_DIFF[np.where(loop_DIFF<val)] = val
            val = filters.threshold_otsu(loop_DIFF)
            a = np.where(loop_DIFF > val)
            print('2', timeit.strftime("%H:%M:%S"))
			# find out original index instead of a and b
			# get time and date from file name
            date = image.metadata['acquisition date'].split(' ')[1]
            print('3', timeit.strftime("%H:%M:%S"))
            time = image.metadata['start time'].split(' ')[2]

            coord = [[i, j] for i, j in zip(segmented_dict[key1][0][a], segmented_dict[key1][1][a])]
            temp_dict1 = {'name': name, 'date': date, 'time': time, 'coord': coord}
            print('4', timeit.strftime("%H:%M:%S"))

            new_image = image[segmented_dict[key1][1], segmented_dict[key1][0]][a[0]]
            temp_dict1['type'] = 'raw'
            temp_dict2 = pd.DataFrame.from_dict(temp_dict1)
            temp_dict3 = pd.DataFrame(columns=image.metadata['wavelength'], data=new_image.tolist())
            column_df = pd.concat([temp_dict2, temp_dict3], axis=1)
            df_collector[name] = column_df
            print('5', timeit.strftime("%H:%M:%S"))

            new_image = rad_image[segmented_dict[key1][1], segmented_dict[key1][0]][a[0]]
            temp_dict1['type'] = 'rad'
            temp_dict2 = pd.DataFrame.from_dict(temp_dict1)
            temp_dict3 = pd.DataFrame(columns=image.metadata['wavelength'], data=new_image.tolist())
            column_df = pd.concat([temp_dict2, temp_dict3], axis=1)
            df_collector[name] = df_collector[name].append(column_df)
            print('6', timeit.strftime("%H:%M:%S"))

            new_image = refle_img[segmented_dict[key1][1], segmented_dict[key1][0]][a[0]]
            temp_dict1['type'] = 'ref'
            temp_dict2 = pd.DataFrame.from_dict(temp_dict1)
            temp_dict3 = pd.DataFrame(columns=image.metadata['wavelength'], data=new_image.tolist())
            column_df = pd.concat([temp_dict2, temp_dict3], axis=1)
            df_collector[name] = df_collector[name].append(column_df)
            print('7', timeit.strftime("%H:%M:%S"))

        dfx = pd.concat([df for df in df_collector.values()], ignore_index=True)

        return dfx


    def calibration_sql(name, data):
        date = image.metadata['acquisition date'].split(' ')[1]
        time = image.metadata['start time'].split(' ')[2]
		# ranger = [(i, j) for i, j in zip(np.arange(ref_y_start, ref_y_stop), np.arange(ref_x_start, ref_x_stop))]
        temp_dict1 = {'name': name, 'date': date, 'time': time, 'type': 'rad'}
        temp_dict2 = pd.DataFrame(temp_dict1, index=[0])
        temp_dict3 = pd.DataFrame(data.tolist(), image.metadata['wavelength'])
        column_df = pd.concat([temp_dict2, temp_dict3.T], axis=1, sort=False)
        return column_df


    first_column_df = imgs2sql(first_keys, first_column_names, first_column)
    second_column_df = imgs2sql(second_keys, second_column_names, second_column)
    third_column_df = imgs2sql(third_keys, third_column_names, third_column)
    forth_column_df = imgs2sql(forth_keys, forth_column_names, forth_column)
    spectralon_df = calibration_sql('spectralon', spectralon_avg)
    black_df = calibration_sql('black', black_avg)
	# stack everything
    frames = [first_column_df, second_column_df, third_column_df, forth_column_df, spectralon_df, black_df]
    all_df = pd.concat(frames, sort=False)

    df_float = all_df.select_dtypes(include=['float'])
    df_float_converted = df_float.apply(pd.to_numeric,downcast='float')
    type_df = all_df['type'].astype('category')
    name_df = all_df['name'].astype('category')
    date_df = pd.to_datetime(all_df['date'])

    df2 = pd.concat((name_df,date_df,type_df,all_df['time'],all_df['coord'],df_float_converted,),axis =1,sort=False)
    print (ROI[:-7])
    
    del image
    del cal_img
    del rad_image
    del refle_img
    timeit.sleep(20)
    df2.to_pickle(ROI[:-7] + 'pickle')
    df2.to_csv(ROI[:-7] + 'csv')
#all_df.to_csv(r'N:\Shahar\test automatic method\pickle4.csv', sep=',')
#all_df.to_hdf(r'N:\Shahar\test automatic method\pickle3.h5', key='all_df', mode='w')


# The files
#for i in range (22,23,1):
#    path = r'D:\to do\2018-09-' + str(i)
#    DARKS = [file for file in glob.glob(path + '\*\*\DARKREF' +'*.hdr', recursive=True)]
#    ROIS = [file for file in glob.glob(path + '\*\ROI.txt', recursive=True)]
#    IMAGES = [file for file in glob.glob(path + '\*\*\*' + 'emptyname' +'*.hdr', recursive=True) if not os.path.basename(file).startswith(('DARKREF','RADIANCE'))]
#
#    for DARK,ROI,IMAGE1 in zip(DARKS,ROIS,IMAGES):
#        cut_images_in_fldr(DARK,ROI,IMAGE1)
  
DARK = r'D:\DONE\todo\emptyname_2018-09-19_17-06-16\capture\DARKREF_emptyname_2018-09-19_17-06-16.hdr'
ROI = r'D:\DONE\todo\emptyname_2018-09-19_17-06-16\ROI.txt'
IMAGE1 = r'D:\DONE\todo\emptyname_2018-09-19_17-06-16\capture\emptyname_2018-09-19_17-06-16.hdr'
cut_images_in_fldr(DARK,ROI,IMAGE1)    
