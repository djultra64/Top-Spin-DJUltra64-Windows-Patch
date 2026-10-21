-- Original delta recipe only; game tables are supplied locally, never embedded.
-- Author: djultra64. Run only after the Python caller verifies source hashes.
local function loadtable(path, scenes)
 local environment={Scenes=scenes or {}}
 local chunk=assert(loadfile(path));setfenv(chunk,environment);chunk()
 return environment
end
local data=loadtable(arg[1]).SceneData
local events=loadtable(arg[2]).Scenes
assert(type(data)=='table' and type(events.newmain)=='table','Missing main menu')
local controls=data.Controls
assert(table.getn(controls)==210 and table.getn(events.newmain.Controls)==210,'Unexpected control count')
assert(controls[150].Name=='Exhibition' and controls[161].Name=='RootOptions','Unexpected control indices')
assert(events.newmain.Controls[161].Down=="$Selection_Exhibition('MoveDown')")
assert(events.newmain.Controls[150].Up=="$Selection_Options('MoveUp')")
local function clone(value)
 if type(value)~='table' then return value end
 local result={};for key,item in pairs(value) do result[key]=clone(item) end;return result
end
local original_data=clone(data)
local original_events=clone(events.newmain)
local function find(nodes,name)
 for _,node in ipairs(nodes) do if node.Name==name then return node end end
 error('Missing expected node: '..name)
end
local function floatread(bytes,at)
 local a,b,c,d=string.byte(bytes,at),string.byte(bytes,at+1),string.byte(bytes,at+2),string.byte(bytes,at+3)
 local bits=a+b*256+c*65536+d*16777216
 local sign=1;if bits>=2147483648 then sign=-1;bits=bits-2147483648 end
 if bits==0 then return 0 end
 local exponent=math.floor(bits/8388608);local fraction=math.mod(bits,8388608)
 assert(exponent>0 and exponent<255,'Expected normal coordinate')
 return sign*(1+fraction/8388608)*2^(exponent-127)
end
local function floatwrite(value)
 local sign=0;if value<0 then sign=2147483648;value=-value end
 local bits=sign
 if value~=0 then
  local mantissa,exponent=math.frexp(value)
  bits=bits+(exponent+126)*8388608+math.floor((mantissa*2-1)*8388608+0.5)
 end
 return string.char(math.mod(bits,256),math.mod(math.floor(bits/256),256),math.mod(math.floor(bits/65536),256),math.mod(math.floor(bits/16777216),256))
end
local main=data.Graph.Children[2].Children[3]
assert(main.Name=='main','Unexpected parent node')
-- The original absolute main-node tracks reset translateY to zero. Change
-- only their three fixed scalar values alongside the initial translation.
local original_animation=data.AnimationData.ClipsKeyframeData
local animation_file=assert(io.open(arg[5],'wb'));animation_file:write(original_animation);animation_file:close()
assert(table.getn(data.AnimationData.OrderedNames)==12 and data.AnimationData.OrderedNames[12]=='main')
local animation=original_animation
local function replace_y(bytes,at)
 assert(string.sub(bytes,at+1,at+4)==string.rep(string.char(0),4),'Unexpected original vertical position')
 return string.sub(bytes,1,at)..floatwrite(24)..string.sub(bytes,at+5)
end
assert(string.len(main.PositioningInfo)==48)
main.PositioningInfo=replace_y(main.PositioningInfo,4)
for _,start in ipairs({2944,3824,6240}) do
 local header=string.char(11)..string.rep(string.char(0),7)..string.char(10)..string.rep(string.char(0),3)
 assert(string.sub(animation,start+1,start+12)==header,'Unexpected animation node index')
 -- The fourth single-key track must be translateY (ordered key type 2).
 local track=string.char(2,0,0,0,1)..string.rep(string.char(0),7)
 assert(string.sub(animation,start+61,start+72)==track,'Unexpected main translateY track')
 animation=replace_y(animation,start+72)
end
data.AnimationData.ClipsKeyframeData=animation
local nodes=main.Children
local original_text=find(nodes,'pht_options')
local original_group=find(nodes,'group_options')
local static_group=find(nodes,'group_exhibition')
local text=clone(original_text)
text.Name='pht_quit';text.TextID='ct_quit'
-- A 40-unit final row fits below Options without moving existing animated rows.
-- Follow the original 4-degree slant by advancing x about 2.797 units.
local delta_x=40*math.tan(math.rad(4));local delta_y=-40
text.LPM=floatwrite(floatread(original_text.LPM,1)+delta_x)..floatwrite(floatread(original_text.LPM,5)+delta_y)..string.sub(original_text.LPM,9)
local group=clone(static_group)
group.Name='group_quit';group.IsAnimated=false
local position=original_group.PositioningInfo or original_group.LPM
assert(string.len(position)==48 and string.len(static_group.LPM)==48)
group.LPM=floatwrite(floatread(position,1)+delta_x)..floatwrite(floatread(position,5)+delta_y)..string.sub(static_group.LPM,9)
group.Children=clone(original_group.Children)
assert(table.getn(group.Children)==1 and group.Children[1].TemplateName=='SelectedText')
local selected=group.Children[1]
selected.Name='PortableQuitSelectedText:Menu'
selected.ChangedAttributes.Menu.ControlName='group_quit'
selected.ChangedAttributes['Menu|Interface|Color_pht_content|pht_content'].TextID='ct_quit'
table.insert(nodes,text);table.insert(nodes,group)
table.insert(controls,{Name='QuitGame',NodeName='pht_quit'})
table.insert(controls,{Name='group_quit',NodeName='PortableQuitSelectedText:Menu'})
table.insert(controls,{Name='group_quit|SelectedText',NodeName='PortableQuitSelectedText:Menu'})
for _,node in ipairs({text,group,selected}) do
 local counts=assert(data.NodeTypes[node.Flags]);counts[node.Type]=assert(counts[node.Type])+1
end
assert(not data.Actions['Selection_Quit(sound)'] and not data.Actions.QuitGame)
data.Actions['Selection_Quit(sound)']={{"PlaySound('@sound@')"},{"SetActiveControl('QuitGame')","this.HighlightSelected('group_quit', 'text')"}}
data.Actions.QuitGame={{"PlaySound('Validate')"},{"this.DjultraQuitGame('djultra64.quit-game')"}}
local bindings=events.newmain.Controls
bindings[161].Down="$Selection_Quit('MoveDown')"
bindings[150].Up="$Selection_Quit('MoveUp')"
bindings[211]=clone(bindings[161])
bindings[211].AButton='$QuitGame';bindings[211].Start='$QuitGame'
bindings[211].Up="$Selection_Options('MoveUp')"
bindings[211].Down="$Selection_Exhibition('MoveDown')"
bindings[212]={};bindings[213]={}
local function literal(value)
 local kind=type(value)
 if kind=='string' then
  local result={'"'}
  for i=1,string.len(value) do table.insert(result,string.format('\\%03d',string.byte(value,i))) end
  table.insert(result,'"');return table.concat(result)
 elseif kind=='number' then return string.format('%.17g',value)
 elseif kind=='boolean' then return tostring(value)
 elseif kind=='table' then
  local keys={};for key,_ in pairs(value) do table.insert(keys,key) end
  table.sort(keys,function(a,b) if type(a)==type(b) then return a<b end;return type(a)<type(b) end)
  local result={'{'}
  for _,key in ipairs(keys) do table.insert(result,'['..literal(key)..']='..literal(value[key])..',') end
  table.insert(result,'}');return table.concat(result)
 end
 error('Unexpected data type: '..kind)
end
local function write(path,source)
 local chunk=assert(loadstring(source,'@djultra64-main-menu-quit'))
 local handle=assert(io.open(path,'wb'));handle:write(string.dump(chunk));handle:close()
end
write(arg[3],'SceneData='..literal(data))
write(arg[4],'Scenes.newmain='..literal(events.newmain))
local checked=loadtable(arg[3]).SceneData
local checked_events=loadtable(arg[4]).Scenes.newmain
assert(table.getn(checked.Controls)==213 and checked.Controls[211].Name=='QuitGame')
assert(checked_events.Controls[211].AButton=='$QuitGame')
-- Compare normalized reloaded tables against the complete original tables.
-- This catches damage outside the intended delta, including binary animation.
local function equal(a,b)
 if type(a)~=type(b) then return false end
 if type(a)~='table' then return a==b end
 for key,value in pairs(a) do if not equal(value,b[key]) then return false end end
 for key,_ in pairs(b) do if a[key]==nil then return false end end
 return true
end
local normalized=clone(checked)
assert(normalized.Graph.Children[2].Children[3].PositioningInfo==main.PositioningInfo)
assert(normalized.AnimationData.ClipsKeyframeData==animation)
normalized.Graph.Children[2].Children[3].PositioningInfo=original_data.Graph.Children[2].Children[3].PositioningInfo
normalized.AnimationData.ClipsKeyframeData=original_animation
for i=1,3 do table.remove(normalized.Controls) end
for i=1,2 do table.remove(normalized.Graph.Children[2].Children[3].Children) end
for _,node in ipairs({text,group,selected}) do
 local counts=normalized.NodeTypes[node.Flags];counts[node.Type]=counts[node.Type]-1
end
normalized.Actions['Selection_Quit(sound)']=nil;normalized.Actions.QuitGame=nil
assert(equal(normalized,original_data),'Unexpected scene data delta')
local normalized_events=clone(checked_events)
for i=1,3 do table.remove(normalized_events.Controls) end
normalized_events.Controls[161].Down=original_events.Controls[161].Down
normalized_events.Controls[150].Up=original_events.Controls[150].Up
assert(equal(normalized_events,original_events),'Unexpected input event delta')
print('QUIT_MENU_COMPILED_AND_RELOADED')
