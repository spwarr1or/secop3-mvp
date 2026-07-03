from __future__ import annotations


# Catálogo local inicial. Se mantiene en código para que el dashboard funcione
# sin descargar información antes de que el usuario ejecute un análisis.
DEPARTMENT_CITIES: dict[str, list[str]] = {
    "Amazonas": ["Leticia", "Puerto Nariño"],
    "Antioquia": ["Medellín", "Abejorral", "Apartadó", "Bello", "Caucasia", "Envigado", "Itagüí", "Rionegro", "Turbo"],
    "Arauca": ["Arauca", "Arauquita", "Saravena", "Tame"],
    "Atlántico": ["Barranquilla", "Baranoa", "Malambo", "Puerto Colombia", "Soledad"],
    "Bolívar": ["Cartagena", "Arjona", "Magangué", "Mompós", "Turbaco"],
    "Boyacá": ["Tunja", "Chiquinquirá", "Duitama", "Paipa", "Sogamoso"],
    "Caldas": ["Manizales", "Chinchiná", "La Dorada", "Riosucio", "Villamaría"],
    "Caquetá": ["Florencia", "Cartagena del Chairá", "San Vicente del Caguán"],
    "Casanare": ["Yopal", "Aguazul", "Monterrey", "Paz de Ariporo", "Villanueva"],
    "Cauca": ["Popayán", "Bolívar", "Santander de Quilichao", "Silvia"],
    "Cesar": ["Valledupar", "Aguachica", "Agustín Codazzi", "Bosconia"],
    "Chocó": ["Quibdó", "Acandí", "Istmina", "Nuquí", "Riosucio"],
    "Córdoba": ["Montería", "Cereté", "Lorica", "Sahagún", "Tierralta"],
    "Cundinamarca": ["Agua de Dios", "Chía", "Facatativá", "Fusagasugá", "Girardot", "Soacha", "Zipaquirá"],
    "Distrito Capital de Bogotá": ["Bogotá"],
    "Guainía": ["Inírida"],
    "Guaviare": ["San José del Guaviare", "Calamar", "El Retorno", "Miraflores"],
    "Huila": ["Neiva", "Garzón", "La Plata", "Pitalito"],
    "La Guajira": ["Riohacha", "Maicao", "Manaure", "Uribia", "Villanueva"],
    "Magdalena": ["Santa Marta", "Ciénaga", "El Banco", "Fundación", "Plato"],
    "Meta": ["Villavicencio", "Acacías", "Granada", "Puerto López"],
    "Nariño": ["Pasto", "Córdoba", "Ipiales", "La Unión", "Tumaco", "Túquerres"],
    "Norte de Santander": ["Cúcuta", "Ocaña", "Pamplona", "Villa del Rosario"],
    "Putumayo": ["Mocoa", "Orito", "Puerto Asís", "Valle del Guamuez"],
    "Quindío": ["Armenia", "Calarcá", "Circasia", "La Tebaida", "Montenegro"],
    "Risaralda": ["Pereira", "Dosquebradas", "La Virginia", "Santa Rosa de Cabal"],
    "San Andrés, Providencia y Santa Catalina": ["San Andrés", "Providencia"],
    "Santander": ["Bucaramanga", "Barrancabermeja", "Floridablanca", "Girón", "Piedecuesta"],
    "Sucre": ["Sincelejo", "Corozal", "Sampués", "San Marcos", "Tolú"],
    "Tolima": ["Ibagué", "Chaparral", "Espinal", "Honda", "Melgar"],
    "Valle del Cauca": ["Cali", "Buenaventura", "Buga", "Cartago", "Palmira", "Tuluá", "Yumbo"],
    "Vaupés": ["Mitú"],
    "Vichada": ["Puerto Carreño", "Cumaribo", "La Primavera", "Santa Rosalía"],
}


def departments() -> list[str]:
    return sorted(DEPARTMENT_CITIES)


def cities_for_department(department: str) -> list[str]:
    return DEPARTMENT_CITIES.get(department, [])
