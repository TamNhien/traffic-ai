import test from 'node:test'
import assert from 'node:assert/strict'
import {recordedDate, reportBucketLabel, reportChartGeometry, reportFilterProblem, reportQuery, reportUrl, shiftReportDate, validateTrafficReport} from '../src/traffic-report-utils.js'

const filters = changes => ({start:'2026-10-01',endInclusive:'2026-10-16',groupBy:'day',cameraId:'',sessionId:'',vehicleType:'',...changes})
const counts = (inside=0,outside=0,unknown=0) => ({total:inside+outside+unknown,in:inside,out:outside,unknown})
const report = () => ({filters:{clock:'recorded',timezone:'Asia/Ho_Chi_Minh'},summary:{...counts(2,3,1),session_count:1,camera_count:1,peak_hour:{bucket:'2026-10-16T12:00:00+07:00',...counts(2,3,1)}},series:[{bucket:'2026-10-16',...counts(2,3,1)}],per_camera:[{camera_id:1,camera_name:'Camera A',...counts(2,3,1)}],per_class:[{vehicle_type:'motorcycle',...counts(2,3,1)}],peak_hours:[{bucket:'2026-10-16T12:00:00+07:00',...counts(2,3,1)}]})

test('inclusive local end date is translated once to server exclusive end; session is explicit',()=>{
  const query=new URLSearchParams(reportQuery(filters({cameraId:'2',sessionId:'193',vehicleType:'truck'})))
  assert.equal(query.get('start'),'2026-10-01')
  assert.equal(query.get('end'),'2026-10-17')
  assert.equal(query.get('camera_id'),'2')
  assert.equal(query.get('session_id'),'193')
  assert.equal(query.get('vehicle_type'),'truck')
  assert.equal(query.get('group_by'),'day')
  assert.equal(new URLSearchParams(reportQuery(filters())).has('session_id'),false)
})

test('UTC+7 recorded dates cross UTC midnight independently of host timezone',()=>{
  assert.equal(recordedDate('2026-10-15T16:59:59Z'),'2026-10-15')
  assert.equal(recordedDate('2026-10-15T17:00:00Z'),'2026-10-16')
  assert.equal(recordedDate('2026-10-15T17:00:00'),'2026-10-16')
  assert.equal(recordedDate('2026-10-16T01:00:00+07:00'),'2026-10-16')
  for(const value of ['',null,'invalid'])assert.equal(recordedDate(value),'')
})

test('date arithmetic handles leap days and year boundaries without DST assumptions',()=>{
  assert.equal(shiftReportDate('2028-02-28',1),'2028-02-29')
  assert.equal(shiftReportDate('2028-02-29',1),'2028-03-01')
  assert.equal(shiftReportDate('2026-12-31',1),'2027-01-01')
  for(const value of ['2026-02-29','2026-02-30','2026-13-01','10/01/2026'])assert.throws(()=>shiftReportDate(value,1))
})

test('report range caps count inclusive days and preserve a valid empty-data day',()=>{
  assert.equal(reportFilterProblem(filters({start:'2026-10-16',endInclusive:'2026-10-16',groupBy:'hour'})),'')
  assert.equal(reportFilterProblem(filters({start:'2026-01-01',endInclusive:'2027-01-01'})),'')
  assert.match(reportFilterProblem(filters({start:'2026-01-01',endInclusive:'2027-01-02'})),/366/)
  assert.equal(reportFilterProblem(filters({start:'2026-10-01',endInclusive:'2026-10-31',groupBy:'hour'})),'')
  assert.match(reportFilterProblem(filters({start:'2026-10-01',endInclusive:'2026-11-01',groupBy:'hour'})),/31/)
  assert.match(reportFilterProblem(filters({start:'2026-10-17',endInclusive:'2026-10-16'})),/Ngày kết thúc/)
  assert.match(reportFilterProblem(filters({start:'9999-12-30',endInclusive:'9999-12-31'})),/ngoài phạm vi/)
  assert.match(reportFilterProblem(filters({start:'0001-01-01',endInclusive:'0001-01-02'})),/ngoài phạm vi/)
})

test('unknown group, vehicle, unsafe ID or injected query values never reach report routes',()=>{
  for(const change of [{groupBy:'year'},{vehicleType:'__proto__'},{vehicleType:'truck&camera_id=2'},{cameraId:'1&session_id=9'},{cameraId:'-1'},{sessionId:'1.5'},{sessionId:'2147483648'},{sessionId:'9007199254740992'}])assert.throws(()=>reportQuery(filters(change)))
})

test('export routes use same query and whitelist real server formats',()=>{
  const query=reportQuery(filters({sessionId:'193'}))
  assert.equal(reportUrl(query),`/api/reports/traffic?${query}`)
  for(const format of ['csv','xlsx','pdf'])assert.equal(reportUrl(query,format),`/api/reports/traffic/export?${query}&format=${format}`)
  assert.throws(()=>reportUrl(query,'html'))
  assert.throws(()=>reportUrl(query,'csv&format=pdf'))
})

test('report response validates counts, unknown-direction partition, clock and time-series sum',()=>{
  const data=report(), before=JSON.stringify(data)
  assert.equal(validateTrafficReport(data),data)
  assert.equal(JSON.stringify(data),before)
  for(const mutation of [r=>{r.summary.total=7},r=>{r.summary.in=-1},r=>{r.per_camera[0].out=NaN},r=>{r.series[0].total=5},r=>{r.summary.total='6'},r=>{r.filters.clock='video_timecode'},r=>{r.filters.timezone='UTC'},r=>{r.summary.peak_hour.total=NaN}]){
    const malformed=report();mutation(malformed);assert.throws(()=>validateTrafficReport(malformed))
  }
})

test('zero traffic is a valid aggregate with no peak, never a synthetic Recall/F1 score',()=>{
  const data={filters:{clock:'recorded',timezone:'Asia/Ho_Chi_Minh'},summary:{...counts(),session_count:0,camera_count:0,peak_hour:null},series:[{bucket:'2026-10-16',...counts()}],per_camera:[],per_class:[],peak_hours:[]}
  assert.equal(validateTrafficReport(data),data)
  assert.equal('recall' in data.summary,false)
  assert.equal('f1' in data.summary,false)
})

test('chart geometry preserves gaps as actual zero rows and handles a single bucket',()=>{
  const geometry=reportChartGeometry([{bucket:'a',...counts(2)},{bucket:'b',...counts()},{bucket:'c',...counts(1,3)}])
  assert.equal(geometry.maximum,4)
  assert.equal(geometry.points[1].total,0)
  assert.equal(geometry.y(0),geometry.top+geometry.plotHeight)
  assert.equal(geometry.points[0].x,geometry.left)
  assert.equal(geometry.points[2].x,geometry.left+geometry.plotWidth)
  const single=reportChartGeometry([{bucket:'a',...counts(2)}])
  assert.equal(single.points[0].x,single.left+single.plotWidth/2)
})

test('empty or malformed graph input produces no NaN/Infinity coordinates',()=>{
  for(const input of [null,[],[{bucket:'a',total:NaN,in:-4,out:Infinity}]]){
    const chart=reportChartGeometry(input)
    assert.equal(Number.isFinite(chart.maximum),true)
    assert.doesNotMatch(JSON.stringify(chart.paths),/NaN|Infinity/)
  }
})

test('bucket labels retain day and month context for multi-day peak hours',()=>{
  assert.equal(reportBucketLabel('2026-10-16T21:00:00+07:00','hour'),'16/10 21h')
  assert.equal(reportBucketLabel('2026-10-16','day'),'16/10/2026')
  assert.equal(reportBucketLabel('2026-10','month'),'10/2026')
  assert.equal(reportBucketLabel('<script>'),'—')
})
