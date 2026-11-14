import {insertGridsBatchQ, getGridsByFarmIdQ} from '../repositories/gridRepository.js';
import db from '../db.js';
export const assignGridsToFarmS= async(farmId,rows=2,cols=2,cellSizeinMeters=400)=>{
     const existingGrids = await getGridsByFarmIdQ(farmId);
    if (existingGrids && existingGrids.length > 0) {
        return existingGrids;
    }
    
    const farmResult= await db.query(
        'SELECT id,center_latitude,center_longitude FROM farms WHERE id= $1',[farmId]);

    if(farmResult.rows.length ==0){
        throw new Error(`Farm with id ${farmId} not found`);
    }
    const {center_latitude,center_longitude}= farmResult.rows[0];
    const centerlat= Number(center_latitude);
    const centerlong= Number(center_longitude);
    //convert cell size in meters into latitude and longitude data 

    const latitudeDelta= cellSizeinMeters/111000;
    const longitudeDelta= cellSizeinMeters/(111000*Math.cos((centerlat*Math.PI)/180));

    const totalLatitudeSpan= rows * latitudeDelta;
    const totalLongitudeSpan= cols* longitudeDelta;

    const startLatitude= centerlat-totalLatitudeSpan/2;
    const startLongitude= centerlong-totalLongitudeSpan/2;

    const generatedGrids=[];
    const rowLabels=['A','B','C','D','E'];

    for(let r= 0; r<rows; r++){
        for (let c= 0; c< cols; c++){
            const min_lat = Number((startLatitude + r*latitudeDelta).toFixed(6));
            const max_lat= Number((startLatitude + (r+1) * latitudeDelta).toFixed(6));
            const min_lon=Number((startLongitude + c* longitudeDelta).toFixed(6));
            const max_lon=Number((startLongitude + (c+1)*  longitudeDelta).toFixed(6));

            const rowChar = rowLabels[r] || `R${r+1}`;
            const colNum= c+1;
            const grid_code=`F${farmId}-${rowChar}${colNum}`;
            generatedGrids.push({
                farm_id: farmId,
                grid_code,
                min_lat,
                max_lat,
                min_lon,
                max_lon,
            });
        }
    }
        
 return insertGridsBatchQ(generatedGrids);   
}
