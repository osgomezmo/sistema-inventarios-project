// Rack selectivo 3D de una bodega sobre su piso demarcado. Cada posición es una estiba
// con cajas proporcionales al saldo; elegir una posición la selecciona también en la tabla.
import { Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { Html, OrbitControls, Text } from '@react-three/drei'
import * as THREE from 'three'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import type { Saldo } from '../api/types'
import { productoPorSku } from '../api/mock/maestros'
import { cantidad, dinero } from '../lib/formato'
import { ANCHO_MODULO, MEDIDAS, distribuir, geometriaCajas, geometriaEstiba, geometriaRack, type DistribucionRack, type Posicion } from './rack'
import { texturas } from './texturas'
import fuenteRotulo from '@fontsource/barlow-condensed/files/barlow-condensed-latin-700-normal.woff?url'
import fuenteEstencil from '@fontsource/big-shoulders-stencil-display/files/big-shoulders-stencil-display-latin-800-normal.woff?url'

const AZUL_PARAL = '#1f4e9c'
const NARANJA_LARGUERO = '#f26a1b'

export const hayWebGL = (() => {
  try {
    const c = document.createElement('canvas')
    return !!(c.getContext('webgl2') || c.getContext('webgl'))
  } catch {
    return false
  }
})()

const reducirMovimiento = () => typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches

interface Props {
  saldos: Saldo[]
  codigoBodega: string
  nombreBodega: string
  seleccionado: string | null
  onSeleccionar: (sku: string | null) => void
  onVerKardex?: (sku: string) => void
  alto?: number | string
  /** false en la portada: sin rotar, sin zoom y sin selección. */
  interactivo?: boolean
}

export function RackBodega(props: Props) {
  const { saldos, codigoBodega, nombreBodega, alto = 460, seleccionado, interactivo = true } = props
  const d = useMemo(() => distribuir(saldos, codigoBodega), [saldos, codigoBodega])
  const bajos = saldos.filter((s) => s.bajo_minimo).length
  const [sobre, setSobre] = useState<string | null>(null)
  const destacado = d.posiciones.find((p) => p.saldo.sku === (sobre ?? seleccionado))

  if (!hayWebGL) {
    return (
      <div className="rack-sin-3d" style={{ height: alto }}>
        <p>Este equipo no puede mostrar el rack en 3D. La tabla de abajo tiene la misma información.</p>
      </div>
    )
  }

  return (
    <div className="rack-3d" style={{ height: alto }} role="img" aria-label={`Rack 3D de ${nombreBodega}: ${d.posiciones.length} posiciones en ${d.niveles} niveles, ${bajos} en stock bajo. La tabla de stock tiene la misma información.`}>
      <Canvas shadows={{ type: THREE.PCFShadowMap }} dpr={[1, 1.75]} frameloop="demand" camera={{ fov: 30, near: 0.1, far: 120, position: [12, 6, 16] }} onPointerMissed={() => props.onSeleccionar(null)}>
        <color attach="background" args={['#dcdcd7']} />
        <fog attach="fog" args={['#dcdcd7', 26, 55]} />
        <Suspense fallback={null}>
          <Escena {...props} d={d} sobre={sobre} setSobre={setSobre} />
        </Suspense>
      </Canvas>
      {interactivo && (destacado
        ? <Rotulo p={destacado} fijo={seleccionado === destacado.saldo.sku} onVerKardex={props.onVerKardex} />
        : <p className="rack-ayuda">Elige una posición para ver su rótulo</p>)}
      <div className="rack-leyenda" aria-hidden>
        <span><i className="ley-normal" />Normal</span>
        <span><i className="ley-bajo" />Stock bajo</span>
        <span><i className="ley-agotado" />Agotado</span>
        <span className="ley-escala">5 cajas = stock mínimo</span>
      </div>
    </div>
  )
}

function Escena({ d, seleccionado, onSeleccionar, codigoBodega, interactivo = true, sobre, setSobre }: Props & { d: DistribucionRack; sobre: string | null; setSobre: (s: string | null) => void }) {
  const rack = useMemo(() => geometriaRack(d), [d])
  const t = texturas()

  useEffect(() => {
    document.body.style.cursor = sobre ? 'pointer' : ''
    return () => { document.body.style.cursor = '' }
  }, [sobre])

  const centroX = d.largo / 2

  return (
    <>
      <hemisphereLight args={['#ffffff', '#b9b9b3', 1.1]} />
      <directionalLight
        position={[centroX - 6, 14, 10]}
        intensity={1.9}
        castShadow
        shadow-mapSize={[2048, 2048]}
        shadow-camera-left={-12}
        shadow-camera-right={12}
        shadow-camera-top={10}
        shadow-camera-bottom={-6}
        shadow-bias={-0.0004}
      />

      <Camara d={d} clave={codigoBodega} interactivo={interactivo} />

      {/* Piso de concreto con su demarcación */}
      <mesh rotation-x={-Math.PI / 2} position={[centroX, 0, 4]} receiveShadow>
        <planeGeometry args={[70, 46]} />
        <meshStandardMaterial map={t.concreto} roughness={0.95} />
      </mesh>
      {[MEDIDAS.fondo / 2 + 0.55, MEDIDAS.fondo / 2 + 3.6].map((z) => (
        <mesh key={z} rotation-x={-Math.PI / 2} position={[centroX, 0.003, z]}>
          <planeGeometry args={[d.largo + 7, 0.1]} />
          <meshStandardMaterial color="#ffc72c" roughness={0.6} />
        </mesh>
      ))}
      <Text font={fuenteEstencil} fontSize={0.42} color="#17181b" fillOpacity={0.72} rotation-x={-Math.PI / 2} position={[-1.6, 0.004, MEDIDAS.fondo / 2 + 2.1]} anchorX="center" anchorY="middle">
        {`PASILLO ${codigoBodega}`}
      </Text>

      {/* Estructura del rack */}
      <mesh geometry={rack.parales} castShadow receiveShadow>
        <meshStandardMaterial color={AZUL_PARAL} roughness={0.45} metalness={0.25} />
      </mesh>
      <mesh geometry={rack.largueros} castShadow receiveShadow>
        <meshStandardMaterial color={NARANJA_LARGUERO} roughness={0.4} metalness={0.2} />
      </mesh>
      {rack.protectores.map(([x, z]) => (
        <mesh key={x} position={[x, 0.22, z]} castShadow>
          <boxGeometry args={[0.16, 0.44, 0.06]} />
          <meshStandardMaterial map={t.franja} roughness={0.6} />
        </mesh>
      ))}

      {/* Letrero de cada tramo, colgado bajo el larguero de arriba: texto HTML para que se lea a cualquier distancia */}
      {d.segmentos.map((s) => (
        <Html
          key={`${s.nivel}-${s.categoria}`}
          position={[segmentoX(s.desde) + 0.06, (s.nivel + 1) * MEDIDAS.nivel - 0.24, MEDIDAS.fondo / 2 + 0.05]}
          zIndexRange={[1, 0]}
          style={{ pointerEvents: 'none' }}
        >
          <span className="rack-cat">N{s.nivel + 1} · {s.categoria}</span>
        </Html>
      ))}

      <Pilas d={d} seleccionado={seleccionado} sobre={sobre} setSobre={interactivo ? setSobre : () => {}} onSeleccionar={interactivo ? onSeleccionar : () => {}} />
    </>
  )
}

const segmentoX = (desde: number) => Math.floor(desde / 2) * (ANCHO_MODULO + MEDIDAS.paral) + MEDIDAS.paral + (desde % 2) * MEDIDAS.posicion

function Pilas({ d, seleccionado, sobre, setSobre, onSeleccionar }: {
  d: DistribucionRack
  seleccionado: string | null
  sobre: string | null
  setSobre: (s: string | null) => void
  onSeleccionar: (sku: string | null) => void
}) {
  const t = texturas()
  const estiba = geometriaEstiba()
  const grupos = useRef<Array<THREE.Group | null>>([])
  const inicio = useRef(0)
  const { invalidate, clock } = useThree()

  useEffect(() => {
    inicio.current = reducirMovimiento() ? -10 : clock.getElapsedTime()
    invalidate()
  }, [d, clock, invalidate])

  // Las pilas crecen una sola vez al mostrar la bodega.
  useFrame(({ clock: c }) => {
    const transcurrido = c.getElapsedTime() - inicio.current
    let falta = false
    grupos.current.forEach((g, i) => {
      if (!g) return
      const avance = THREE.MathUtils.clamp((transcurrido - i * 0.045) / 0.55, 0, 1)
      const e = 1 - Math.pow(1 - avance, 3)
      g.scale.y = Math.max(e, 0.001)
      if (avance < 1) falta = true
    })
    if (falta) invalidate()
  })

  return (
    <>
      {d.posiciones.map((p, i) => {
        const geo = geometriaCajas(p.cajas)
        const activo = seleccionado === p.saldo.sku
        const encima = sobre === p.saldo.sku
        const agotado = p.saldo.cantidad === 0
        return (
          <group key={p.codigo} position={[p.x, p.y, 0]}>
            <group
              onPointerOver={(e) => { e.stopPropagation(); setSobre(p.saldo.sku) }}
              onPointerOut={() => setSobre(null)}
              onClick={(e) => { e.stopPropagation(); onSeleccionar(activo ? null : p.saldo.sku) }}
            >
              <mesh geometry={estiba} castShadow receiveShadow>
                <meshStandardMaterial map={t.madera} roughness={0.85} />
              </mesh>
              <group ref={(g) => {
                grupos.current[i] = g
                if (g && !g.userData.iniciado) { g.userData.iniciado = true; g.scale.y = 0.001 }
              }}>
                {geo && (
                  <mesh geometry={geo} castShadow receiveShadow>
                    <meshStandardMaterial map={t.carton} roughness={0.9} />
                  </mesh>
                )}
              </group>
              {/* volumen invisible para apuntar con el mouse aunque la estiba esté vacía */}
              <mesh position={[0, 0.7, 0]} visible={activo || encima}>
                <boxGeometry args={[1.28, 1.4, 1.04]} />
                <meshBasicMaterial color="#ffc72c" transparent opacity={activo ? 0.2 : 0.14} depthWrite={false} />
              </mesh>
            </group>
            {activo && <MarcoSeleccion />}
            <Etiqueta p={p} activo={activo} agotado={agotado} />
          </group>
        )
      })}
    </>
  )
}

/** Marco amarillo de la posición elegida: el amarillo es el color de la selección en toda la interfaz. */
function MarcoSeleccion() {
  const w = 1.34, h = 1.46, d = 1.08, g = 0.05
  const barras: Array<[number, number, number, number, number, number]> = []
  for (const x of [-w / 2, w / 2]) for (const z of [-d / 2, d / 2]) barras.push([x, h / 2, z, g, h, g])
  for (const y of [0.02, h]) {
    for (const z of [-d / 2, d / 2]) barras.push([0, y, z, w, g, g])
    for (const x of [-w / 2, w / 2]) barras.push([x, y, 0, g, g, d])
  }
  return (
    <group>
      {barras.map(([x, y, z, sx, sy, sz], i) => (
        <mesh key={i} position={[x, y, z]}>
          <boxGeometry args={[sx, sy, sz]} />
          <meshBasicMaterial color="#ffc72c" />
        </mesh>
      ))}
    </group>
  )
}

/** Franja de peligro con rayas anchas para un rótulo de ancho × alto (en metros). */
const franjas = new Map<string, THREE.Texture>()
function franjaParaPlaca(ancho: number, alto: number) {
  const clave = `${ancho}x${alto}`
  if (!franjas.has(clave)) {
    const tex = texturas().franja.clone()
    tex.repeat.set(ancho / 0.6, alto / 0.6)
    tex.needsUpdate = true
    franjas.set(clave, tex)
  }
  return franjas.get(clave)!
}

/** Rótulo de ubicación: en el larguero de abajo, o pintado en el piso para el nivel 1. */
function Etiqueta({ p, activo, agotado }: { p: Posicion; activo: boolean; agotado: boolean }) {
  const bajo = p.saldo.bajo_minimo && !agotado
  const enPiso = p.nivel === 0
  const fondo = activo ? '#ffc72c' : agotado ? '#c2311e' : '#ffffff'
  const tinta = agotado && !activo ? '#ffffff' : '#17181b'

  if (enPiso) {
    return (
      <group position={[0, 0.004, MEDIDAS.fondo / 2 + 0.36]} rotation-x={-Math.PI / 2}>
        {(bajo || agotado) && (
          <mesh position={[0, 0, -0.001]}>
            <planeGeometry args={[1.3, 0.46]} />
            {agotado ? <meshStandardMaterial color="#c2311e" /> : <meshStandardMaterial map={franjaParaPlaca(1.3, 0.46)} />}
          </mesh>
        )}
        <mesh>
          <planeGeometry args={[1.04, 0.28]} />
          <meshStandardMaterial color={fondo} />
        </mesh>
        <Text font={fuenteEstencil} fontSize={0.19} color={tinta} anchorX="center" anchorY="middle" position={[0, 0, 0.002]}>
          {p.codigo}
        </Text>
      </group>
    )
  }

  return (
    <group position={[0, -MEDIDAS.larguero / 2, MEDIDAS.fondo / 2 + 0.006]}>
      {bajo && (
        <mesh position={[0, 0, -0.001]}>
          <planeGeometry args={[1.28, 0.3]} />
          <meshStandardMaterial map={franjaParaPlaca(1.28, 0.3)} />
        </mesh>
      )}
      <mesh>
        <planeGeometry args={[1.02, 0.19]} />
        <meshStandardMaterial color={fondo} />
      </mesh>
      <Text font={fuenteRotulo} fontSize={0.145} color={tinta} anchorX="center" anchorY="middle" position={[0, 0, 0.002]}>
        {p.codigo}
      </Text>
    </group>
  )
}

/** Rótulo de la posición destacada, fijo en la esquina del rack para que nunca quede cortado. */
function Rotulo({ p, fijo, onVerKardex }: { p: Posicion; fijo: boolean; onVerKardex?: (sku: string) => void }) {
  const prod = productoPorSku.get(p.saldo.sku)!
  const agotado = p.saldo.cantidad === 0
  return (
    <div className="rotulo-3d" role="status" aria-live="polite">
      <div className="rotulo-cabeza">
        <strong>{p.saldo.sku}</strong>
        <span>{p.codigo}</span>
      </div>
      <p className="rotulo-nombre">{prod.nombre} · {p.categoria}</p>
      <p className="rotulo-cantidad cifra">{cantidad(p.saldo.cantidad, prod.unidad_medida)}</p>
      <p className="rotulo-dato">
        {agotado ? <span className="tag tag-agotado">Agotado</span> : p.saldo.bajo_minimo ? <span className="tag tag-bajo">Stock bajo</span> : <span className="tag">Normal</span>}
        <span>Mínimo {cantidad(p.saldo.stock_minimo, prod.unidad_medida)}</span>
      </p>
      <p className="rotulo-dato"><span>Costo prom. {dinero(p.saldo.costo_promedio)}</span><span>Valor {dinero(p.saldo.valor)}</span></p>
      {fijo && onVerKardex && <button type="button" className="btn btn-sm btn-oscuro" onClick={() => onVerKardex(p.saldo.sku)}>Ver kardex</button>}
    </div>
  )
}

/** Encuadra el rack; al cambiar de bodega la cámara se desliza al nuevo rack. */
function Camara({ d, clave, interactivo }: { d: DistribucionRack; clave: string; interactivo: boolean }) {
  const controles = useRef<OrbitControlsImpl>(null)
  const { camera, invalidate, size } = useThree()
  const meta = useMemo(() => {
    const objetivo = new THREE.Vector3(d.largo / 2, d.alto * 0.42, 0)
    const aspecto = size.width / Math.max(size.height, 1)
    const vertical = THREE.MathUtils.degToRad(30)
    const distAlto = (d.alto * 1.25) / 2 / Math.tan(vertical / 2)
    const distAncho = (d.largo * 1.12) / 2 / Math.tan(vertical / 2) / aspecto
    const dist = Math.max(distAlto, distAncho, 9)
    const posicion = objetivo.clone().add(new THREE.Vector3(0.36, 0.3, 0.88).normalize().multiplyScalar(dist))
    return { objetivo, posicion, dist }
  }, [d, size.width, size.height])

  const animando = useRef(false)
  const primera = useRef(true)

  useEffect(() => {
    if (primera.current || reducirMovimiento()) {
      camera.position.copy(meta.posicion)
      controles.current?.target.copy(meta.objetivo)
      controles.current?.update()
      primera.current = false
    } else {
      animando.current = true
    }
    invalidate()
  }, [clave, meta, camera, invalidate])

  useFrame((_, delta) => {
    if (!animando.current || !controles.current) return
    const c = controles.current
    camera.position.x = THREE.MathUtils.damp(camera.position.x, meta.posicion.x, 4, delta)
    camera.position.y = THREE.MathUtils.damp(camera.position.y, meta.posicion.y, 4, delta)
    camera.position.z = THREE.MathUtils.damp(camera.position.z, meta.posicion.z, 4, delta)
    c.target.lerp(meta.objetivo, 1 - Math.exp(-4 * delta))
    c.update()
    if (camera.position.distanceTo(meta.posicion) < 0.02) animando.current = false
    invalidate()
  })

  return (
    <OrbitControls
      ref={controles}
      makeDefault
      enablePan={false}
      enableRotate={interactivo}
      enableZoom={interactivo}
      enableDamping
      minDistance={meta.dist * 0.45}
      maxDistance={meta.dist * 1.35}
      minPolarAngle={0.95}
      maxPolarAngle={1.48}
      minAzimuthAngle={-0.75}
      maxAzimuthAngle={0.9}
    />
  )
}
